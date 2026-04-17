from datetime import datetime, timezone

from fastapi import APIRouter

from app.schemas import HealthResponse


router = APIRouter(tags=["health"])


@router.get("/api/health", response_model=HealthResponse)
def health_check() -> HealthResponse:
    return HealthResponse(service="llm-watch", time=datetime.now(timezone.utc))
