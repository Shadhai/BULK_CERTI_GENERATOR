"""API key authentication on write endpoints."""

import pytest


@pytest.fixture
def with_api_key(monkeypatch):
    from app.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "api_key", "test-key-123", raising=False)
    yield "test-key-123"


def _payload():
    return {"recipients": [{"name": "Alice"}]}


def test_create_job_requires_key_when_enabled(client, with_api_key):
    response = client.post("/api/v1/jobs", json=_payload())
    assert response.status_code == 401
    assert response.headers.get("www-authenticate") == "ApiKey"


def test_create_job_rejects_wrong_key(client, with_api_key):
    response = client.post(
        "/api/v1/jobs", json=_payload(), headers={"X-API-Key": "wrong"}
    )
    assert response.status_code == 401


def test_create_job_accepts_correct_key(client, with_api_key):
    response = client.post(
        "/api/v1/jobs",
        json=_payload(),
        headers={"X-API-Key": "test-key-123"},
    )
    assert response.status_code == 202


def test_reads_are_open_even_with_api_key_set(client, with_api_key):
    job_id = client.post(
        "/api/v1/jobs",
        json=_payload(),
        headers={"X-API-Key": "test-key-123"},
    ).json()["id"]
    assert client.get(f"/api/v1/jobs/{job_id}").status_code == 200


def test_retry_requires_key(client, with_api_key, run_jobs_inline):
    job_id = client.post(
        "/api/v1/jobs",
        json=_payload(),
        headers={"X-API-Key": "test-key-123"},
    ).json()["id"]
    run_jobs_inline(job_id)

    assert client.post(f"/api/v1/jobs/{job_id}/retry").status_code == 401
    response = client.post(
        f"/api/v1/jobs/{job_id}/retry",
        headers={"X-API-Key": "test-key-123"},
    )
    assert response.status_code == 202


def test_auth_disabled_when_api_key_unset(client, monkeypatch):
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "api_key", None, raising=False)
    assert client.post("/api/v1/jobs", json=_payload()).status_code == 202
