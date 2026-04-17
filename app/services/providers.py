from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.adapters.base import AdapterError
from app.adapters.dashscope import DashScopeAdapter
from app.adapters.deepseek import DeepSeekAdapter
from app.adapters.qianfan import QianfanAdapter
from app.config import get_settings
from app.models import Model, Provider


ADAPTERS = {
    "deepseek": DeepSeekAdapter,
    "dashscope": DashScopeAdapter,
    "qianfan": QianfanAdapter,
}


def get_provider_rows(db: Session) -> Sequence[Provider]:
    stmt = select(Provider).options(selectinload(Provider.models)).order_by(Provider.id)
    return db.scalars(stmt).all()


def get_provider_and_model(db: Session, provider_key: str, model_key: str | None = None) -> tuple[Provider, Model]:
    stmt = (
        select(Provider)
        .options(selectinload(Provider.models))
        .where(Provider.provider_key == provider_key)
    )
    provider = db.scalars(stmt).first()
    if provider is None:
        raise AdapterError(f"Unknown provider '{provider_key}'.", code="unknown_provider")
    if not provider.enabled:
        raise AdapterError(f"Provider '{provider_key}' is disabled.", code="provider_disabled")

    model = None
    if model_key:
        model = next((item for item in provider.models if item.model_key == model_key and item.enabled), None)
    else:
        model = next((item for item in provider.models if item.enabled), None)
    if model is None:
        raise AdapterError(
            f"Model '{model_key or 'default'}' for provider '{provider_key}' was not found.",
            code="unknown_model",
        )
    return provider, model


def get_adapter(provider_key: str):
    adapter_cls = ADAPTERS.get(provider_key)
    if adapter_cls is None:
        raise AdapterError(f"Unsupported provider '{provider_key}'.", code="unsupported_provider")
    return adapter_cls()


def list_provider_configs(db: Session) -> list[dict]:
    settings = get_settings()
    providers = []
    for provider in get_provider_rows(db):
        config = settings.provider_defaults.get(provider.provider_key, {})
        providers.append(
            {
                "provider": provider.provider_key,
                "provider_name": provider.provider_name,
                "base_url": provider.base_url,
                "models": [model.model_key for model in provider.models if model.enabled],
                "enabled": bool(provider.enabled),
                "api_key_configured": bool(config.get("api_key")),
            }
        )
    return providers
