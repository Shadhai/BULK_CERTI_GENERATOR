"""Crash recovery: stale processing jobs are requeued and resumed safely."""


from datetime import timedelta

from app.database import SessionLocal
from app.models import Certificate, CertificateStatus, Job, JobStatus, utcnow


def test_stale_processing_job_is_requeued(client):
    from app.worker import recover_stale_jobs

    job_id = client.post(
        "/api/v1/jobs", json={"recipients": [{"name": "Alice"}]}
    ).json()["id"]

    db = SessionLocal()
    try:
        job = db.get(Job, job_id)
        job.status = JobStatus.PROCESSING
        job.started_at = utcnow() - timedelta(hours=1)
        db.commit()
    finally:
        db.close()

    db = SessionLocal()
    try:
        recovered = recover_stale_jobs(db)
    finally:
        db.close()

    assert recovered >= 1
    assert client.get(f"/api/v1/jobs/{job_id}").json()["status"] == "queued"


def test_resume_skips_already_successful_rows(client, run_jobs_inline):
    """
    A job that was interrupted mid-way (status back to queued) should only
    render the still-pending rows, leaving completed work untouched.
    """
    payload = {"recipients": [{"name": f"Person {i}"} for i in range(5)]}
    job_id = client.post("/api/v1/jobs", json=payload).json()["id"]

    # Simulate "two rows already done" before the worker resumes.
    db = SessionLocal()
    try:
        first_two = (
            db.query(Certificate)
            .filter(Certificate.job_id == job_id)
            .order_by(Certificate.row_index)
            .limit(2)
            .all()
        )
        for cert in first_two:
            cert.status = CertificateStatus.SUCCESS
            cert.storage_path = f"{job_id}/{cert.id}.pdf"
            cert.checksum = "deadbeef" * 8  # sentinel
        job = db.get(Job, job_id)
        job.status = JobStatus.QUEUED
        db.commit()
    finally:
        db.close()

    run_jobs_inline(job_id)

    body = client.get(f"/api/v1/jobs/{job_id}").json()
    assert body["counts"]["success"] == 5
    assert body["counts"]["pending"] == 0

    # The two sentinel rows were not re-rendered.
    sentinel_rows = (
        client.get(f"/api/v1/jobs/{job_id}/certificates").json()["items"]
    )
    sentinel_checksums = {r["checksum"] for r in sentinel_rows}
    assert "deadbeef" * 8 in sentinel_checksums