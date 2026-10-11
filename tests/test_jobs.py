"""Job creation + input validation."""


def _recipient(i: int) -> dict:
    return {
        "name": f"Person {i}",
        "email": f"person{i}@example.com",
        "course_name": "Python Fundamentals",
        "issue_date": "2024-01-15",
    }


def test_create_job_returns_202_with_pending_rows(client):
    payload = {"recipients": [_recipient(i) for i in range(5)]}
    resp = client.post("/api/v1/jobs", json=payload)

    assert resp.status_code == 202
    body = resp.json()
    assert body["status"] == "queued"
    assert body["counts"]["total"] == 5
    assert body["counts"]["pending"] == 5
    assert body["counts"]["success"] == 0

    # Certificates are visible immediately (as pending rows).
    listing = client.get(f"/api/v1/jobs/{body['id']}/certificates").json()
    assert listing["total"] == 5
    assert all(item["status"] == "pending" for item in listing["items"])


def test_oversized_batch_rejected_with_422(client):
    payload = {"recipients": [{"name": "X"} for _ in range(5001)]}
    resp = client.post("/api/v1/jobs", json=payload)
    assert resp.status_code == 422
    assert "max size" in resp.json()["detail"].lower()


def test_empty_recipients_rejected(client):
    resp = client.post("/api/v1/jobs", json={"recipients": []})
    assert resp.status_code == 422


def test_missing_recipients_key_rejected(client):
    resp = client.post("/api/v1/jobs", json={})
    assert resp.status_code == 422


def test_invalid_rows_are_isolated_not_rejected(client):
    """The brief's key requirement: 3 bad rows must not fail the whole job."""
    payload = {
        "recipients": [
            {"name": "Alice"},
            {"name": ""},  # invalid: empty name
            {"name": "Bob", "email": "not-an-email"},  # invalid: bad email
            {"name": "Carol", "issue_date": "not-a-date"},  # invalid: bad date
            {"name": "Dave", "course_name": "Go"},  # valid
        ]
    }
    resp = client.post("/api/v1/jobs", json=payload)
    assert resp.status_code == 202
    body = resp.json()
    assert body["counts"]["total"] == 5
    assert body["counts"]["invalid"] == 3
    assert body["counts"]["pending"] == 2

    invalid = client.get(
        f"/api/v1/jobs/{body['id']}/certificates?status=invalid"
    ).json()
    assert invalid["total"] == 3
    # Reasons are actionable, not generic.
    reasons = {item["row_index"]: item["error"] for item in invalid["items"]}
    assert "name is required" in reasons[1]
    assert "email" in reasons[2]
    assert "issue_date" in reasons[3]


def test_unknown_job_returns_404(client):
    assert client.get("/api/v1/jobs/does-not-exist").status_code == 404