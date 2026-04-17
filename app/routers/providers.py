from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas import ChatRequest, ChatResponse, ProviderTestRequest, ProvidersResponse
from app.services.providers import get_adapter, get_provider_and_model, list_provider_configs


router = APIRouter(tags=["providers"])


@router.get("/api/providers", response_model=ProvidersResponse)
def get_providers(db: Session = Depends(get_db)) -> ProvidersResponse:
    return ProvidersResponse(items=list_provider_configs(db))


@router.post("/api/providers/test", response_model=ChatResponse)
async def test_provider(payload: ProviderTestRequest, db: Session = Depends(get_db)) -> ChatResponse:
    _, model = get_provider_and_model(db, payload.provider, payload.model)
    adapter = get_adapter(payload.provider)
    result = await adapter.chat(model.model_key, [{"role": "user", "content": "ping"}], stream=False, max_tokens=8, temperature=0)
    return ChatResponse(
        provider=result.provider,
        model=result.model,
        content=result.content,
        usage=result.usage,
        timing=result.timing,
        http_status=result.http_status,
        raw=result.raw,
    )


@router.post("/api/chat", response_model=ChatResponse)
async def chat(payload: ChatRequest, db: Session = Depends(get_db)) -> ChatResponse:
    _, model = get_provider_and_model(db, payload.provider, payload.model)
    adapter = get_adapter(payload.provider)
    result = await adapter.chat(
        model.model_key,
        [item.model_dump() for item in payload.messages],
        stream=payload.stream,
        max_tokens=payload.max_tokens,
        temperature=payload.temperature,
    )
    return ChatResponse(
        provider=result.provider,
        model=result.model,
        content=result.content,
        usage=result.usage,
        timing=result.timing,
        http_status=result.http_status,
        raw=result.raw,
    )
