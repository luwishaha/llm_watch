import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.adapters.base import AdapterError
from app.config import get_settings
from app.db import SessionLocal
from app.routers import evals, health, pages, probes, providers
from app.schemas import ErrorResponse
from app.services.dashboard_service import get_compare, get_summary
from app.services.probe_service import ensure_default_jobs, run_health_probe, update_job_run_state
from app.services.providers import list_enabled_provider_keys, sync_provider_defaults_from_settings


scheduler = BackgroundScheduler(timezone="UTC")
BASE_DIR = Path(__file__).resolve().parent


def _scheduled_health_probe() -> None:
    db = SessionLocal()
    try:
        sync_provider_defaults_from_settings(db)
        provider_keys = list_enabled_provider_keys(db)
        if provider_keys:
            asyncio.run(run_health_probe(db, provider_keys))
        settings = get_settings()
        next_run = datetime.now(timezone.utc) + timedelta(minutes=settings.scheduler_health_interval_minutes)
        update_job_run_state(db, "health_probe", next_run)
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    db = SessionLocal()
    try:
        sync_provider_defaults_from_settings(db)
        ensure_default_jobs(db)
    finally:
        db.close()

    if settings.scheduler_health_enabled and not scheduler.running:
        scheduler.add_job(
            _scheduled_health_probe,
            "interval",
            minutes=settings.scheduler_health_interval_minutes,
            id="health_probe",
            replace_existing=True,
        )
        scheduler.start()

    yield

    if scheduler.running:
        scheduler.shutdown(wait=False)


app = FastAPI(title="llm-watch", version="0.1.0", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
app.include_router(health.router)
app.include_router(providers.router)
app.include_router(probes.router)
app.include_router(evals.router)
app.include_router(pages.router)


@app.get("/api/dashboard/summary")
def dashboard_summary():
    db = SessionLocal()
    try:
        sync_provider_defaults_from_settings(db)
        return {"success": True, "summary": get_summary(db)}
    finally:
        db.close()


@app.get("/api/dashboard/compare")
def dashboard_compare(providers: str | None = None, window: str = "24h"):
    db = SessionLocal()
    try:
        sync_provider_defaults_from_settings(db)
        provider_list = [item.strip() for item in providers.split(",") if item.strip()] if providers else list_enabled_provider_keys(db)
        return {"success": True, "compare": get_compare(db, provider_list, window)}
    finally:
        db.close()


@app.exception_handler(AdapterError)
async def adapter_error_handler(_: Request, exc: AdapterError):
    payload = ErrorResponse(error={"code": exc.code, "message": exc.message, "detail": exc.detail})
    return JSONResponse(status_code=exc.http_status or 400, content=payload.model_dump())


@app.exception_handler(Exception)
async def generic_error_handler(_: Request, exc: Exception):
    payload = ErrorResponse(error={"code": "internal_error", "message": str(exc), "detail": None})
    return JSONResponse(status_code=500, content=payload.model_dump())
