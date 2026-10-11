"""Happy-path generation, retrieval, and PDF assertions."""


def test_full_generation_completes_and_serves_pdfs(client, run_jobs_inline):
    payload = {
        "recipients": [
            {
                "name": "Alice Example",
                "email": "alice@example.com",
                "course_name": "Python",
                "issue_date": "2024-03-01",
            },
            {"name": "Bob Example", "course_name": "Python", "issue_date": "2024-03-01"},
        ]
    }
    job_id = client.post("/api/v1/jobs", json=payload).json()["id"]

    run_jobs_inline(job_id)

    status = client.get(f"/api/v1/jobs/{job_id}").json()
    assert status["status"] == "completed"
    assert status["counts"] == {
        "total": 2,
        "pending": 0,
        "success": 2,
        "failed": 0,
        "invalid": 0,
    }
    assert status["started_at"] is not None
    assert status["finished_at"] is not None

    certs = client.get(f"/api/v1/jobs/{job_id}/certificates").json()["items"]
    assert len(certs) == 2
    assert all(c["status"] == "success" for c in certs)
    assert all(c["checksum"] for c in certs)  # deterministic output
    assert all(c["download_url"] for c in certs)

    # Single-certificate download
    pdf_resp = client.get(f"/api/v1/certificates/{certs[0]['id']}")
    assert pdf_resp.status_code == 200
    assert pdf_resp.headers["content-type"].startswith("application/pdf")
    assert pdf_resp.content.startswith(b"%PDF")
    assert len(pdf_resp.content) > 1000

    # ZIP download
    zip_resp = client.get(f"/api/v1/jobs/{job_id}/download")
    assert zip_resp.status_code == 200
    assert zip_resp.headers["content-type"] == "application/zip"
    assert zip_resp.content[:2] == b"PK"


def test_download_pending_certificate_returns_409(client):
    job_id = client.post(
        "/api/v1/jobs", json={"recipients": [{"name": "Nobody"}]}
    ).json()["id"]
    certs = client.get(f"/api/v1/jobs/{job_id}/certificates").json()["items"]
    resp = client.get(f"/api/v1/certificates/{certs[0]['id']}")
    assert resp.status_code == 409


def test_status_endpoint_reflects_counts(client, run_jobs_inline):
    payload = {
        "recipients": [
            {"name": "Valid One"},
            {"name": ""},  # invalid
            {"name": "Valid Two"},
        ]
    }
    job_id = client.post("/api/v1/jobs", json=payload).json()["id"]
    run_jobs_inline(job_id)

    body = client.get(f"/api/v1/jobs/{job_id}").json()
    assert body["counts"]["success"] == 2
    assert body["counts"]["invalid"] == 1
    assert body["status"] == "completed_with_errors"


def test_pagination_and_status_filter(client, run_jobs_inline):
    payload = {"recipients": [{"name": f"P{i}"} for i in range(10)]}
    job_id = client.post("/api/v1/jobs", json=payload).json()["id"]
    run_jobs_inline(job_id)

    page1 = client.get(
        f"/api/v1/jobs/{job_id}/certificates?page=1&size=3"
    ).json()
    assert len(page1["items"]) == 3
    assert page1["total"] == 10
    assert page1["pages"] == 4

    page4 = client.get(
        f"/api/v1/jobs/{job_id}/certificates?page=4&size=3"
    ).json()
    assert len(page4["items"]) == 1