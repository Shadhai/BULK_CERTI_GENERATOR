"""One bad certificate must not poison the rest of the job."""


def test_single_render_failure_is_isolated(client, run_jobs_inline, monkeypatch):
    from app import rendering, worker

    original = rendering.render_certificate

    def flaky(*, recipient_name, **kwargs):
        if recipient_name == "Poison":
            raise RuntimeError("simulated render failure")
        return original(recipient_name=recipient_name, **kwargs)

    monkeypatch.setattr(worker, "render_certificate", flaky)

    payload = {
        "recipients": [
            {"name": "Good One"},
            {"name": "Poison"},
            {"name": "Good Two"},
        ]
    }
    job_id = client.post("/api/v1/jobs", json=payload).json()["id"]
    run_jobs_inline(job_id)

    body = client.get(f"/api/v1/jobs/{job_id}").json()
    assert body["status"] == "completed_with_errors"
    assert body["counts"]["success"] == 2
    assert body["counts"]["failed"] == 1
    assert body["counts"]["pending"] == 0

    failed = client.get(
        f"/api/v1/jobs/{job_id}/certificates?status=failed"
    ).json()["items"]
    assert len(failed) == 1
    assert failed[0]["recipient_name"] == "Poison"
    assert "simulated render failure" in failed[0]["error"]


def test_every_recipient_failing_still_completes(client, run_jobs_inline, monkeypatch):
    from app import rendering, worker

    def always_fail(*, recipient_name, **kwargs):
        raise rendering.RenderError("nope")

    monkeypatch.setattr(worker, "render_certificate", always_fail)

    payload = {"recipients": [{"name": f"R{i}"} for i in range(5)]}
    job_id = client.post("/api/v1/jobs", json=payload).json()["id"]
    run_jobs_inline(job_id)

    body = client.get(f"/api/v1/jobs/{job_id}").json()
    assert body["status"] == "completed_with_errors"
    assert body["counts"]["failed"] == 5
    assert body["counts"]["success"] == 0