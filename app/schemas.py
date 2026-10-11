from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field

from app.models import CertificateStatus, JobStatus


class JobCreateRequest(BaseModel):
    """
    Recipients are accepted as raw dicts on purpose.

    Declaring ``list[RecipientIn]`` would make FastAPI reject the entire request
    on the first bad row. We want per-row isolation: a job with 3 bad rows out
    of 1000 must be accepted, with 3 rows marked ``invalid``.
    """

    recipients: list[dict[str, Any]] = Field(..., min_length=1)
    template_id: str = "default"


class JobCounts(BaseModel):
    total: int
    pending: int
    success: int
    failed: int
    invalid: int


class JobResponse(BaseModel):
    id: str
    status: JobStatus
    template_id: str
    counts: JobCounts
    error_message: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


class CertificateResponse(BaseModel):
    id: str
    job_id: str
    row_index: int
    recipient_name: str | None
    recipient_email: str | None
    course_name: str | None
    issue_date: date | None
    status: CertificateStatus
    error: str | None
    checksum: str | None
    download_url: str | None


class CertificateListResponse(BaseModel):
    items: list[CertificateResponse]
    total: int
    page: int
    size: int
    pages: int