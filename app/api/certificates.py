import os
import tempfile
import zipfile
from collections.abc import Iterator

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Certificate, CertificateStatus, Job
from app.storage import get_storage

router = APIRouter(prefix="/api/v1", tags=["certificates"])


def _safe_filename(name: str, cert_id: str) -> str:
    cleaned = "".join(
        ch for ch in (name or "certificate") if ch.isalnum() or ch in (" ", "-", "_")
    ).strip()
    cleaned = cleaned or "certificate"
    return f"{cleaned[:80]}_{cert_id[:8]}.pdf"


@router.get("/certificates/{cert_id}", summary="Download a single certificate PDF")
def download_certificate(cert_id: str, db: Session = Depends(get_db)):
    cert = db.get(Certificate, cert_id)
    if cert is None:
        raise HTTPException(status_code=404, detail="certificate not found")
    if cert.status != CertificateStatus.SUCCESS or not cert.storage_path:
        raise HTTPException(
            status_code=409,
            detail=f"certificate is not available (status={cert.status.value})",
        )

    path = get_storage().full_path(cert.storage_path)
    if not path.exists():
        raise HTTPException(status_code=410, detail="certificate file is missing")

    return FileResponse(
        path,
        media_type="application/pdf",
        filename=_safe_filename(cert.recipient_name or "", cert.id),
    )


def _stream_file(path: str, chunk: int = 64 * 1024) -> Iterator[bytes]:
    """Yield file bytes and unlink on completion (or client disconnect)."""
    try:
        with open(path, "rb") as fh:
            while True:
                data = fh.read(chunk)
                if not data:
                    break
                yield data
    finally:
        try:
            os.unlink(path)
        except FileNotFoundError:
            pass


@router.get("/jobs/{job_id}/download", summary="Download all successful certificates as a ZIP")
def download_zip(job_id: str, db: Session = Depends(get_db)):
    if db.get(Job, job_id) is None:
        raise HTTPException(status_code=404, detail="job not found")

    certs = (
        db.execute(
            select(Certificate)
            .where(
                Certificate.job_id == job_id,
                Certificate.status == CertificateStatus.SUCCESS,
            )
            .order_by(Certificate.row_index.asc())
        )
        .scalars()
        .all()
    )
    if not certs:
        raise HTTPException(status_code=404, detail="no successful certificates")

    storage = get_storage()

    # Build the ZIP on disk (bounds memory for large jobs), then stream it out.
    tmp = tempfile.NamedTemporaryFile(prefix=f"job_{job_id}_", suffix=".zip", delete=False)
    tmp.close()
    try:
        with zipfile.ZipFile(tmp.name, "w", zipfile.ZIP_DEFLATED) as zf:
            for cert in certs:
                try:
                    with storage.open(cert.storage_path) as fh:
                        zf.writestr(
                            _safe_filename(cert.recipient_name or "", cert.id),
                            fh.read(),
                        )
                except FileNotFoundError:
                    # File was deleted out of band — skip rather than fail the zip.
                    continue
    except Exception:
        os.unlink(tmp.name)
        raise

    return StreamingResponse(
        _stream_file(tmp.name),
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="job_{job_id}.zip"'
        },
    )