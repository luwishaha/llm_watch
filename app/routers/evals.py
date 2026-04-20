from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas import (
    EvalResultsResponse,
    EvalResultItem,
    EvalRunRequest,
    EvalRunResponse,
    EvalSetImportRequest,
    EvalSetImportResponse,
    EvalSetItem,
    EvalSetListResponse,
)
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


@router.get("/api/eval-sets", response_model=EvalSetListResponse)
def get_eval_sets(db: Session = Depends(get_db)) -> EvalSetListResponse:
    items = [EvalSetItem(**item) for item in eval_service.list_eval_sets(db)]
    return EvalSetListResponse(items=items)


@router.post("/api/eval-sets/import-text", response_model=EvalSetImportResponse)
def import_eval_set_from_text(payload: EvalSetImportRequest, db: Session = Depends(get_db)) -> EvalSetImportResponse:
    result = eval_service.import_eval_set_from_text(
        db,
        eval_key=payload.eval_key,
        eval_name=payload.eval_name,
        source_type=payload.source_type,
        content=payload.content,
        enabled=payload.enabled,
    )
    return EvalSetImportResponse(status=result["status"], sample_count=result["sample_count"], item=EvalSetItem(**result["item"]))


@router.post("/api/eval-sets/upload", response_model=EvalSetImportResponse)
async def upload_eval_set(
    file: UploadFile = File(...),
    eval_key: str = Form(...),
    eval_name: str = Form(...),
    source_type: str = Form(...),
    enabled: bool = Form(default=True),
    db: Session = Depends(get_db),
) -> EvalSetImportResponse:
    result = eval_service.import_eval_set_from_upload(
        db,
        eval_key=eval_key,
        eval_name=eval_name,
        source_type=source_type,
        filename=file.filename or "",
        content_bytes=await file.read(),
        enabled=enabled,
    )
    return EvalSetImportResponse(status=result["status"], sample_count=result["sample_count"], item=EvalSetItem(**result["item"]))
