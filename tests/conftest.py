"""
Test bootstrap.

Environment variables are set at import time, before any ``app.*`` module loads,
so ``get_settings()`` and the SQLAlchemy engine see the isolated paths.
"""

import os
import tempfile
from pathlib import Path

_TMP = Path(tempfile.mkdtemp(prefix="bcg-tests-"))
os.environ["BCG_DATABASE_URL"] = f"sqlite:///{_TMP / 'test.db'}"
os.environ["BCG_STORAGE_ROOT"] = str(_TMP / "storage")
os.environ["BCG_WORKER_ENABLED"] = "false"  # tests drive the worker inline
os.environ["BCG_BATCH_CHUNK_SIZE"] = "10"
os.environ["BCG_MAX_BATCH_SIZE"] = "5000"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import delete  # noqa: E402

from app.database import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Certificate, Job  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _schema():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(autouse=True)
def _clean_tables(_schema):
    db = SessionLocal()
    try:
        db.execute(delete(Certificate))
        db.execute(delete(Job))
        db.commit()
    finally:
        db.close()
    yield


@pytest.fixture
def client():
    # No lifespan here: the worker is disabled anyway and tests want a plain client.
    with TestClient(app) as c:
        yield c


@pytest.fixture
def run_jobs_inline():
    """
    Drive the worker synchronously from the test.

    The processing pipeline is a plain function (``process_job``), so calling it
    directly gives deterministic tests with no polling races.
    """
    from app.worker import process_job

    def _run(job_id: str) -> None:
        db = SessionLocal()
        try:
            process_job(db, job_id)
        finally:
            db.close()

    return _run