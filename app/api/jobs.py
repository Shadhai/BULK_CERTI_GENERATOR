from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import Certificate, CertificateStatus, Job, JobStatus
from app.security import require_api_key
from app.schemas import (
    CertificateListResponse,
    CertificateResponse,
    JobCounts,
    JobCreateRequest,
    JobResponse,
)
from app.validation import validate_recipient

router = APIRouter(prefix="/api/v1", tags=["jobs"])


def _counts(db: Session, job_id: str) -> JobCounts:
    """
    Counts are derived, not stored. Incrementing counters from multiple workers
    drifts; a GROUP BY on the (job_id, status) index is trivially cheap and
    always truthful.
    """
    rows = db.execute(
        select(Certificate.status, func.count())
        .where(Certificate.job_id == job_id)
        .group_by(Certificate.status)
    ).all()
    by_status = {row[0]: row[1] for row in rows}

    return JobCounts(
        total=sum(by_status.values()),
        pending=by_status.get(CertificateStatus.PENDING, 0),
        success=by_status.get(CertificateStatus.SUCCESS, 0),
        failed=by_status.get(CertificateStatus.FAILED, 0),
        invalid=by_status.get(CertificateStatus.INVALID, 0),
    )


def _to_response(db: Session, job: Job) -> JobResponse:
    return JobResponse(
        id=job.id,
        status=job.status,
        template_id=job.template_id,
        counts=_counts(db, job.id),
        error_message=job.error_message,
        created_at=job.created_at,
        started_at=job.started_at,
        finished_at=job.finished_at,
    )


def _cert_to_response(cert: Certificate) -> CertificateResponse:
    download_url = (
        f"/api/v1/certificates/{cert.id}"
        if cert.status == CertificateStatus.SUCCESS
        else None
    )
    return CertificateResponse(
        id=cert.id,
        job_id=cert.job_id,
        row_index=cert.row_index,
        recipient_name=cert.recipient_name,
        recipient_email=cert.recipient_email,
        course_name=cert.course_name,
        issue_date=cert.issue_date,
        status=cert.status,
        error=cert.error,
        checksum=cert.checksum,
        download_url=download_url,
    )


@router.post(
    "/jobs",
    response_model=JobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Submit a bulk certificate generation job",
    dependencies=[Depends(require_api_key)],
)
def create_job(payload: JobCreateRequest, db: Session = Depends(get_db)) -> JobResponse:
    settings = get_settings()

    # Envelope-level guard — reject the whole request, not row-by-row.
    if len(payload.recipients) > settings.max_batch_size:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"batch exceeds max size of {settings.max_batch_size} recipients",
        )

    job = Job(
        template_id=payload.template_id or settings.default_template,
        total_count=len(payload.recipients),
        status=JobStatus.QUEUED,
    )
    db.add(job)
    db.flush()  # assign job.id

    for idx, row in enumerate(payload.recipients):
        fields, err = validate_recipient(row, idx)
        if err is not None:
            db.add(
                Certificate(
                    job_id=job.id,
                    row_index=idx,
                    status=CertificateStatus.INVALID,
                    error=err,
                )
            )
        else:
            db.add(
                Certificate(
                    job_id=job.id,
                    row_index=idx,
                    status=CertificateStatus.PENDING,
                    recipient_name=fields["recipient_name"],
                    recipient_email=fields["recipient_email"],
                    course_name=fields["course_name"],
                    issue_date=fields["issue_date"],
                )
            )

    db.commit()
    db.refresh(job)
    return _to_response(db, job)


@router.get("/jobs/{job_id}", response_model=JobResponse)
def get_job(
    job_id: str,
    response: Response,
    db: Session = Depends(get_db),
) -> JobResponse:
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    body = _to_response(db, job)
    if body.status in (JobStatus.QUEUED, JobStatus.PROCESSING):
        response.headers["Retry-After"] = str(get_settings().retry_after_seconds)
    return body


@router.get(
    "/jobs/{job_id}/certificates",
    response_model=CertificateListResponse,
    summary="List per-recipient results (filterable by status)",
)
def list_certificates(
    job_id: str,
    status_filter: str | None = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
) -> CertificateListResponse:
    if db.get(Job, job_id) is None:
        raise HTTPException(status_code=404, detail="job not found")

    stmt = select(Certificate).where(Certificate.job_id == job_id)
    count_stmt = (
        select(func.count()).select_from(Certificate).where(Certificate.job_id == job_id)
    )

    if status_filter:
        try:
            desired = CertificateStatus(status_filter)
        except ValueError:
            raise HTTPException(
                status_code=400, detail=f"unknown status '{status_filter}'"
            ) from None
        stmt = stmt.where(Certificate.status == desired)
        count_stmt = count_stmt.where(Certificate.status == desired)

    total = db.execute(count_stmt).scalar_one()
    rows = (
        db.execute(
            stmt.order_by(Certificate.row_index.asc())
            .offset((page - 1) * size)
            .limit(size)
        )
        .scalars()
        .all()
    )

    return CertificateListResponse(
        items=[_cert_to_response(c) for c in rows],
        total=total,
        page=page,
        size=size,
        pages=max(1, (total + size - 1) // size),
    )


@router.post(
    "/jobs/{job_id}/retry",
    response_model=JobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Requeue only the failed rows of a finished job",
    dependencies=[Depends(require_api_key)],
)
def retry_job(job_id: str, db: Session = Depends(get_db)) -> JobResponse:
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    if job.status in (JobStatus.QUEUED, JobStatus.PROCESSING):
        raise HTTPException(status_code=409, detail="job is still in progress")

    result = db.execute(
        update(Certificate)
        .where(
            Certificate.job_id == job_id,
            Certificate.status == CertificateStatus.FAILED,
        )
        .values(status=CertificateStatus.PENDING, error=None)
    )
    db.commit()

    if (result.rowcount or 0) > 0:
        job.status = JobStatus.QUEUED
        job.started_at = None
        job.finished_at = None
        job.error_message = None
        db.commit()

    db.refresh(job)
    return _to_response(db, job)