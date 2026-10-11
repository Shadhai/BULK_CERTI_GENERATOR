"""Retry reprocesses only failed rows; successful rows are untouched."""


def test_retry_only_requeues_failed_rows(client, run_jobs_inline, monkeypatch):
    from app import rendering, worker

    original = rendering.render_certificate
    state = {"fail": True}

    def flaky(*, recipient_name, **kwargs):
        if state["fail"] and recipient_name == "Flaky":
            raise RuntimeError("transient")
        return original(recipient_name=recipient_name, **kwargs)

    monkeypatch.setattr(worker, "render_certificate", flaky)

    payload = {"recipients": [{"name": "Stable"}, {"name": "Flaky"}]}
    job_id = client.post("/api/v1/jobs", json=payload).json()["id"]
    run_jobs_inline(job_id)

    before = client.get(f"/api/v1/jobs/{job_id}").json()
    assert before["counts"]["success"] == 1
    assert before["counts"]["failed"] == 1

    stable_cert = client.get(
        f"/api/v1/jobs/{job_id}/certificates?status=success"
    ).json()["items"][0]
    original_checksum = stable_cert["checksum"]

    # Fix the world, then retry.
    state["fail"] = False
    resp = client.post(f"/api/v1/jobs/{job_id}/retry")
    assert resp.status_code == 202
    assert resp.json()["status"] == "queued"

    run_jobs_inline(job_id)

    after = client.get(f"/api/v1/jobs/{job_id}").json()
    assert after["status"] == "completed"
    assert after["counts"]["success"] == 2
    assert after["counts"]["failed"] == 0

    # The previously-successful certificate was not re-rendered.
    after_success = client.get(
        f"/api/v1/jobs/{job_id}/certificates?status=success"
    ).json()["items"]
    assert any(item["checksum"] == original_checksum for item in after_success)


def test_retry_conflicts_while_job_in_progress(client):
    """A job that is still queued/processing must not accept a retry."""
    from app.database import SessionLocal
    from app.models import Job, JobStatus

    job_id = client.post(
        "/api/v1/jobs", json={"recipients": [{"name": "X"}]}
    ).json()["id"]

    db = SessionLocal()
    try:
        job = db.get(Job, job_id)
        job.status = JobStatus.PROCESSING
        db.commit()
    finally:
        db.close()

    resp = client.post(f"/api/v1/jobs/{job_id}/retry")
    assert resp.status_code == 409