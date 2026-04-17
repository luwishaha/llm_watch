from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas import (
    CacheProbeRunRequest,
    ProbeRunItem,
    ProbeRunResponse,
    ProbeRunsResponse,
    ProbeRunRequest,
    PerfProbeRunRequest,
)
from app.services import probe_service


router = APIRouter(tags=["probes"])


@router.post("/api/probes/health/run", response_model=ProbeRunResponse)
async def run_health(payload: ProbeRunRequest, db: Session = Depends(get_db)) -> ProbeRunResponse:
    results = await probe_service.run_health_probe(db, payload.providers)
    return ProbeRunResponse(run_type="health", results=results)


@router.post("/api/probes/perf/run", response_model=ProbeRunResponse)
async def run_perf(payload: PerfProbeRunRequest, db: Session = Depends(get_db)) -> ProbeRunResponse:
    results = await probe_service.run_perf_probe(db, payload.providers, payload.prompt_template, payload.max_tokens)
    return ProbeRunResponse(run_type="perf", results=results)


@router.post("/api/probes/cache/run", response_model=ProbeRunResponse)
async def run_cache(payload: CacheProbeRunRequest, db: Session = Depends(get_db)) -> ProbeRunResponse:
    results = await probe_service.run_cache_probe(db, payload.providers, payload.prompt_template)
    return ProbeRunResponse(run_type="cache", results=results)


@router.get("/api/probes/runs", response_model=ProbeRunsResponse)
def get_runs(
    provider: str | None = Query(default=None),
    model: str | None = Query(default=None),
    run_type: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=200),
    db: Session = Depends(get_db),
) -> ProbeRunsResponse:
    runs = probe_service.list_probe_runs(db, provider, model, run_type, limit)
    items = [ProbeRunItem(**run) for run in runs]
    return ProbeRunsResponse(items=items)
