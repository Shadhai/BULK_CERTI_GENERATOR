import logging
import threading
from datetime import timedelta

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import SessionLocal, engine
from app.models import (
    Certificate,
    CertificateStatus,
    Job,
    JobStatus,
    utcnow,
)
from app.rendering import checksum, render_certificate
from app.storage import get_storage

log = logging.getLogger("bcg.worker")


def _supports_skip_locked() -> bool:
    return engine.dialect.name in ("postgresql", "mysql", "mariadb")


def claim_next_job(db: Session) -> Job | None:
    """
    Atomically claim one queued job.

    ``FOR UPDATE SKIP LOCKED`` makes this safe with N concurrent workers; on
    SQLite (single-writer by design) we skip the hint.
    """
    stmt = (
        select(Job)
        .where(Job.status == JobStatus.QUEUED)
        .order_by(Job.created_at.asc())
        .limit(1)
    )
    if _supports_skip_locked():
        stmt = stmt.with_for_update(skip_locked=True)

    job = db.execute(stmt).scalar_one_or_none()
    if job is None:
        return None

    job.status = JobStatus.PROCESSING
    job.started_at = utcnow()
    db.commit()
    return job


def process_job(db: Session, job_id: str) -> None:
    """
    Process every pending certificate row for a job.

    Design notes:
      * Idempotent w.r.t. the claim step: if the caller already claimed the job
        (via ``claim_next_job``), we leave its state alone. If called directly,
        we set status/started_at ourselves.
      * Batches of ``batch_chunk_size`` rows are committed together so progress is
        visible quickly and a crash loses at most one batch.
      * Successful rows are skipped on resume — resume/retry/replay are all the
        same code path thanks to the ``UNIQUE(job_id, row_index)`` constraint.
    """
    job = db.get(Job, job_id)
    if job is None:
        return

    changed = False
    if job.status != JobStatus.PROCESSING:
        job.status = JobStatus.PROCESSING
        changed = True
    if job.started_at is None:
        job.started_at = utcnow()
        changed = True
    if changed:
        db.commit()

    settings = get_settings()
    storage = get_storage()

    pending_ids: list[str] = [
        row[0]
        for row in db.execute(
            select(Certificate.id)
            .where(
                Certificate.job_id == job_id,
                Certificate.status == CertificateStatus.PENDING,
            )
            .order_by(Certificate.row_index.asc())
        ).all()
    ]

    for start in range(0, len(pending_ids), settings.batch_chunk_size):
        chunk_ids = pending_ids[start : start + settings.batch_chunk_size]
        rows = (
            db.execute(select(Certificate).where(Certificate.id.in_(chunk_ids)))
            .scalars()
            .all()
        )
        for cert in rows:
            _process_one(cert, storage)
        db.commit()

    _finalize_job(db, job_id)


def _process_one(cert: Certificate, storage) -> None:
    """Render one certificate. Any failure is contained to this row."""
    try:
        pdf = render_certificate(
            recipient_name=cert.recipient_name or "",
            course_name=cert.course_name,
            issue_date=cert.issue_date,
        )
        rel = storage.put(cert.job_id, cert.id, pdf)
        cert.status = CertificateStatus.SUCCESS
        cert.storage_path = rel
        cert.checksum = checksum(pdf)
        cert.error = None
    except Exception as exc:  # noqa: BLE001 — deliberate containment
        log.warning(
            "certificate render failed",
            extra={"cert_id": cert.id, "job_id": cert.job_id, "row": cert.row_index},
            exc_info=True,
        )
        cert.status = CertificateStatus.FAILED
        cert.error = f"{type(exc).__name__}: {exc}"


def _finalize_job(db: Session, job_id: str) -> None:
    job = db.get(Job, job_id)
    if job is None:
        return

    remaining = db.execute(
        select(func.count())
        .select_from(Certificate)
        .where(
            Certificate.job_id == job_id,
            Certificate.status == CertificateStatus.PENDING,
        )
    ).scalar_one()
    if remaining:
        # Another worker (or a retry) is still processing rows.
        return

    failed = db.execute(
        select(func.count())
        .select_from(Certificate)
        .where(
            Certificate.job_id == job_id,
            Certificate.status.in_(
                [CertificateStatus.FAILED, CertificateStatus.INVALID]
            ),
        )
    ).scalar_one()

    job.status = (
        JobStatus.COMPLETED_WITH_ERRORS if failed else JobStatus.COMPLETED
    )
    job.finished_at = utcnow()
    db.commit()


def recover_stale_jobs(db: Session) -> int:
    """
    Any job left in ``processing`` longer than the timeout is presumed abandoned
    (worker crash, redeploy mid-job) and requeued. Progress is preserved because
    only ``pending`` rows are re-rendered.
    """
    settings = get_settings()
    cutoff = utcnow() - timedelta(seconds=settings.stale_job_timeout_seconds)

    result = db.execute(
        update(Job)
        .where(Job.status == JobStatus.PROCESSING, Job.started_at < cutoff)
        .values(status=JobStatus.QUEUED, started_at=None)
    )
    db.commit()
    return result.rowcount or 0


def run_worker_once(db: Session) -> bool:
    """Claim and process one job. Returns False when nothing was queued."""
    job = claim_next_job(db)
    if job is None:
        return False

    try:
        process_job(db, job.id)
    except Exception as exc:  # noqa: BLE001 — job-level fatality
        log.exception("job crashed", extra={"job_id": job.id})
        db.rollback()
        current = db.get(Job, job.id)
        if current is not None:
            current.status = JobStatus.FAILED
            current.error_message = f"{type(exc).__name__}: {exc}"
            current.finished_at = utcnow()
            db.commit()
    return True


def worker_loop(stop_event: threading.Event) -> None:
    settings = get_settings()
    db = SessionLocal()
    try:
        recovered = recover_stale_jobs(db)
        if recovered:
            log.info("recovered %d stale job(s)", recovered)

        while not stop_event.is_set():
            worked = run_worker_once(db)
            if not worked:
                stop_event.wait(settings.worker_poll_interval)
    finally:
        db.close()


def main() -> None:  # pragma: no cover — CLI entrypoint
    """Run a standalone worker process: ``python -m app.worker``."""
    import signal

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s"
    )
    stop = threading.Event()

    def _handle(_signum, _frame):
        stop.set()

    signal.signal(signal.SIGINT, _handle)
    signal.signal(signal.SIGTERM, _handle)

    log.info("worker starting")
    worker_loop(stop)
    log.info("worker stopped")


if __name__ == "__main__":  # pragma: no cover
    main()