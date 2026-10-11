import logging
import threading
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from app import models  # noqa: F401 — ensure models register with Base
from app.api import certificates as certificates_api
from app.api import jobs as jobs_api
from app.config import get_settings
from app.database import SessionLocal
from app.worker import worker_loop

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
log = logging.getLogger("bcg")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()

    settings.storage_root.mkdir(parents=True, exist_ok=True)

    if not settings.api_key:
        log.warning(
            "BCG_API_KEY is not set — write endpoints are unauthenticated. "
            "Set it before exposing this service."
        )

    stop_event = threading.Event()
    worker_thread: threading.Thread | None = None

    if settings.worker_enabled:
        worker_thread = threading.Thread(
            target=worker_loop, args=(stop_event,), daemon=True, name="bcg-worker"
        )
        worker_thread.start()
        log.info("in-process worker started")
    else:
        log.info("in-process worker disabled (BCG_WORKER_ENABLED=false)")

    try:
        yield
    finally:
        stop_event.set()
        if worker_thread is not None:
            worker_thread.join(timeout=5)


app = FastAPI(
    title="Bulk Certificate Generator",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(jobs_api.router)
app.include_router(certificates_api.router)

STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    """Serve the single-page frontend at the site root."""
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/healthz", tags=["meta"])
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/readyz", tags=["meta"])
def readyz() -> dict[str, str]:
    db = SessionLocal()
    try:
        db.execute(text("SELECT 1"))
    finally:
        db.close()
    return {"status": "ready"}