from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.adapters.base import AdapterError, BaseProviderAdapter
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


def sync_provider_defaults_from_settings(db: Session) -> None:
    settings = get_settings()
    env_providers = settings.provider_defaults
    existing = {provider.provider_key: provider for provider in get_provider_rows(db)}

    for provider_key, config in env_providers.items():
        provider = existing.get(provider_key)
        if provider is None:
            provider = Provider(
                provider_key=provider_key,
                provider_name=str(config["name"]),
                base_url=str(config["base_url"]),
                api_key_env=str(config["api_key_env"]),
                enabled=bool(config.get("enabled", True)),
            )
            db.add(provider)
            db.flush()
            existing[provider_key] = provider
        else:
            provider.provider_name = str(config["name"])
            provider.base_url = str(config["base_url"])
            provider.api_key_env = str(config["api_key_env"])
            provider.enabled = bool(config.get("enabled", True))

        target_model = str(config["model"])
        matched_model = next((item for item in provider.models if item.model_key == target_model), None)
        if matched_model is None:
            matched_model = Model(
                provider_id=provider.id,
                model_key=target_model,
                model_name=target_model,
                enabled=True,
            )
            db.add(matched_model)
            provider.models.append(matched_model)
        else:
            matched_model.model_name = target_model
            matched_model.enabled = True

        for model in provider.models:
            if model is not matched_model:
                model.enabled = False

    for provider_key, provider in existing.items():
        if provider_key in env_providers:
            continue
        provider.enabled = False
        for model in provider.models:
            model.enabled = False

    db.commit()


def get_provider_and_model(db: Session, provider_key: str, model_key: str | None = None) -> tuple[Provider, Model]:
    sync_provider_defaults_from_settings(db)
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
    if adapter_cls is not None:
        return adapter_cls()
    settings = get_settings()
    if provider_key not in settings.provider_defaults:
        raise AdapterError(f"Unsupported provider '{provider_key}'.", code="unsupported_provider")
    return BaseProviderAdapter(provider_key=provider_key)


def list_provider_configs(db: Session) -> list[dict]:
    sync_provider_defaults_from_settings(db)
    settings = get_settings()
    providers = []
    for provider in get_provider_rows(db):
        if provider.provider_key not in settings.provider_defaults:
            continue
        active_models = [model.model_key for model in provider.models if model.enabled]
        config = settings.provider_defaults.get(provider.provider_key, {})
        providers.append(
            {
                "provider": provider.provider_key,
                "provider_name": provider.provider_name,
                "base_url": provider.base_url,
                "default_model": active_models[0] if active_models else "",
                "models": active_models,
                "enabled": bool(provider.enabled),
                "api_key_configured": bool(config.get("api_key")),
                "api_key_env": provider.api_key_env,
            }
        )
    return providers


def list_enabled_provider_keys(db: Session) -> list[str]:
    sync_provider_defaults_from_settings(db)
    return [provider.provider_key for provider in get_provider_rows(db) if provider.enabled]
