from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas import EvalResultsResponse, EvalResultItem, EvalRunRequest, EvalRunResponse
from app.services import eval_service


router = APIRouter(tags=["evals"])


@router.post("/api/evals/run", response_model=EvalRunResponse)
async def run_eval(payload: EvalRunRequest, db: Session = Depends(get_db)) -> EvalRunResponse:
    results = await eval_service.run_eval(db, payload.eval_set, payload.providers)
    return EvalRunResponse(eval_set=payload.eval_set, results=results)


@router.get("/api/evals/results", response_model=EvalResultsResponse)
def get_eval_results(
    eval_set: str | None = Query(default=None),
    provider: str | None = Query(default=None),
    model: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=200),
    db: Session = Depends(get_db),
) -> EvalResultsResponse:
    items = [EvalResultItem(**item) for item in eval_service.list_eval_results(db, eval_set, provider, model, limit)]
    return EvalResultsResponse(items=items)
