"""Retry-After hint on the job status endpoint."""

from app.database import SessionLocal
from app.models import Job, JobStatus


def test_retry_after_present_while_queued(client):
    response = client.post(
        "/api/v1/jobs", json={"recipients": [{"name": "Alice"}]}
    )
    job_id = response.json()["id"]

    status_response = client.get(f"/api/v1/jobs/{job_id}")
    assert status_response.status_code == 200
    assert status_response.headers.get("retry-after") == "2"
    assert status_response.json()["status"] == "queued"


def test_retry_after_present_while_processing(client):
    job_id = client.post(
        "/api/v1/jobs", json={"recipients": [{"name": "Alice"}]}
    ).json()["id"]

    db = SessionLocal()
    try:
        job = db.get(Job, job_id)
        job.status = JobStatus.PROCESSING
        db.commit()
    finally:
        db.close()

    response = client.get(f"/api/v1/jobs/{job_id}")
    assert response.headers.get("retry-after") == "2"


def test_retry_after_absent_when_finished(client, run_jobs_inline):
    job_id = client.post(
        "/api/v1/jobs", json={"recipients": [{"name": "Alice"}]}
    ).json()["id"]
    run_jobs_inline(job_id)

    response = client.get(f"/api/v1/jobs/{job_id}")
    assert response.json()["status"] == "completed"
    assert "retry-after" not in response.headers
