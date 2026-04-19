import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.adapters.base import AdapterError, UnifiedChatResult
from app.models import AppJob, Model, ProbeRun, Provider
from app.services.providers import get_adapter, get_provider_and_model, list_enabled_provider_keys


HEALTH_MESSAGES = [{"role": "user", "content": "ping"}]
PERF_MESSAGES = [
    {"role": "system", "content": "You are a concise assistant."},
    {"role": "user", "content": "请用两句话总结大型语言模型 API 监控平台的目标。"},
]
CACHE_MESSAGES = [
    {
        "role": "user",
        "content": (
            "下面是一段重复的长前缀，请保留理解上下文。\n"
            + ("LLM Watch cache benchmark prefix. " * 80)
            + "\n请只回复一句：cache probe acknowledged."
        ),
    }
]


def ensure_default_jobs(db: Session) -> None:
    defaults = [
        ("health_probe", "Health Probe", "*/5 * * * *", True),
        ("perf_probe", "Perf Probe", "manual", False),
        ("cache_probe", "Cache Probe", "manual", False),
        ("daily_eval", "Daily Eval", "manual", False),
    ]
    existing = {job.job_key: job for job in db.scalars(select(AppJob)).all()}
    for key, name, cron_expr, enabled in defaults:
        if key in existing:
            existing[key].job_name = name
            existing[key].cron_expr = cron_expr
            existing[key].enabled = enabled
        else:
            db.add(AppJob(job_key=key, job_name=name, cron_expr=cron_expr, enabled=enabled))
    db.commit()


async def run_health_probe(db: Session, providers: list[str]) -> list[dict]:
    provider_keys = providers or list_enabled_provider_keys(db)
    results = []
    for provider_key in provider_keys:
        provider, model = get_provider_and_model(db, provider_key)
        adapter = get_adapter(provider_key)
        request_payload = {"messages": HEALTH_MESSAGES, "stream": False, "max_tokens": 8, "temperature": 0}
        try:
            result = await adapter.chat(model.model_key, HEALTH_MESSAGES, stream=False, max_tokens=8, temperature=0)
        except AdapterError as exc:
            result = _adapter_error_result(provider_key, model.model_key, exc)
        run = _persist_probe_run(db, provider, model, "health", request_payload, result)
        results.append(_run_summary(provider.provider_key, model.model_key, run))
    return results


async def run_perf_probe(db: Session, providers: list[str], prompt_template: str, max_tokens: int) -> list[dict]:
    messages = PERF_MESSAGES if prompt_template == "standard_short" else PERF_MESSAGES
    provider_keys = providers or list_enabled_provider_keys(db)
    results = []
    for provider_key in provider_keys:
        provider, model = get_provider_and_model(db, provider_key)
        adapter = get_adapter(provider_key)
        request_payload = {"messages": messages, "stream": True, "max_tokens": max_tokens, "temperature": 0.2}
        try:
            result = await adapter.chat(model.model_key, messages, stream=True, max_tokens=max_tokens, temperature=0.2)
            completion_tokens = result.usage.get("completion_tokens", 0)
            latency_ms = result.timing.get("latency_ms") or 0
            result.usage["completion_tokens"] = completion_tokens
            result.usage["total_tokens"] = result.usage.get("prompt_tokens", 0) + completion_tokens
            if latency_ms > 0 and completion_tokens > 0:
                result.raw["tokens_per_sec"] = round(completion_tokens / (latency_ms / 1000), 2)
        except AdapterError as exc:
            result = _adapter_error_result(provider_key, model.model_key, exc)
        run = _persist_probe_run(db, provider, model, "perf", request_payload, result)
        results.append(_run_summary(provider.provider_key, model.model_key, run))
    return results


async def run_cache_probe(db: Session, providers: list[str], prompt_template: str) -> list[dict]:
    messages = CACHE_MESSAGES if prompt_template == "long_prefix_cache" else CACHE_MESSAGES
    provider_keys = providers or list_enabled_provider_keys(db)
    results = []
    for provider_key in provider_keys:
        provider, model = get_provider_and_model(db, provider_key)
        adapter = get_adapter(provider_key)
        request_payload = {"messages": messages, "stream": False, "max_tokens": 32, "temperature": 0}
        try:
            cold_result = await adapter.chat(model.model_key, messages, stream=False, max_tokens=32, temperature=0)
        except AdapterError as exc:
            cold_result = _adapter_error_result(provider_key, model.model_key, exc)
        cold_run = _persist_probe_run(db, provider, model, "cache", request_payload, cold_result)

        try:
            warm_result = await adapter.chat(model.model_key, messages, stream=False, max_tokens=32, temperature=0)
        except AdapterError as exc:
            warm_result = _adapter_error_result(provider_key, model.model_key, exc)
        warm_run = _persist_probe_run(db, provider, model, "cache", request_payload, warm_result)

        results.append(
            {
                "provider": provider.provider_key,
                "model": model.model_key,
                "cold": _run_summary(provider.provider_key, model.model_key, cold_run),
                "warm": _run_summary(provider.provider_key, model.model_key, warm_run),
                "delta_latency_ms": _delta(cold_run.latency_ms, warm_run.latency_ms),
                "delta_ttft_ms": _delta(cold_run.ttft_ms, warm_run.ttft_ms),
                "cached_tokens": int(warm_run.cached_tokens or 0),
            }
        )
    return results


def list_probe_runs(
    db: Session,
    provider: str | None,
    model: str | None,
    run_type: str | None,
    limit: int,
) -> list[dict]:
    stmt = (
        select(ProbeRun, Provider.provider_key, Model.model_key)
        .select_from(ProbeRun)
        .join(Provider, ProbeRun.provider_id == Provider.id)
        .join(Model, ProbeRun.model_id == Model.id)
    )
    if provider:
        stmt = stmt.where(Provider.provider_key == provider)
    if model:
        stmt = stmt.where(Model.model_key == model)
    if run_type:
        stmt = stmt.where(ProbeRun.run_type == run_type)
    stmt = stmt.order_by(ProbeRun.created_at.desc()).limit(limit)
    rows = db.execute(stmt).all()
    return [
        {
            "id": run.id,
            "provider": provider_key,
            "model": model_key,
            "run_type": run.run_type,
            "success": bool(run.success),
            "http_status": run.http_status,
            "latency_ms": run.latency_ms,
            "ttft_ms": run.ttft_ms,
            "cached_tokens": run.cached_tokens,
            "tokens_per_sec": run.tokens_per_sec,
            "error_type": run.error_type,
            "error_message": run.error_message,
            "created_at": run.created_at,
        }
        for run, provider_key, model_key in rows
    ]


def update_job_run_state(db: Session, job_key: str, next_run_at: datetime | None = None) -> None:
    job = db.scalars(select(AppJob).where(AppJob.job_key == job_key)).first()
    if not job:
        return
    job.last_run_at = datetime.now(timezone.utc)
    job.next_run_at = next_run_at
    db.commit()


def _persist_probe_run(
    db: Session,
    provider: Provider,
    model: Model,
    run_type: str,
    request_payload: dict,
    result: UnifiedChatResult,
) -> ProbeRun:
    latency_ms = result.timing.get("latency_ms")
    ttft_ms = result.timing.get("ttft_ms")
    completion_tokens = int(result.usage.get("completion_tokens", 0))
    tokens_per_sec = None
    if completion_tokens and latency_ms:
        tokens_per_sec = round(completion_tokens / (latency_ms / 1000), 2)

    run = ProbeRun(
        provider_id=provider.id,
        model_id=model.id,
        run_type=run_type,
        success=result.success,
        http_status=result.http_status,
        error_type=result.error,
        error_message=result.raw.get("error_message") if isinstance(result.raw, dict) else None,
        latency_ms=latency_ms,
        ttft_ms=ttft_ms,
        prompt_tokens=int(result.usage.get("prompt_tokens", 0)),
        completion_tokens=completion_tokens,
        total_tokens=int(result.usage.get("total_tokens", 0)),
        cached_tokens=int(result.usage.get("cached_tokens", 0)),
        tokens_per_sec=tokens_per_sec or result.raw.get("tokens_per_sec"),
        request_payload=json.dumps(request_payload, ensure_ascii=False),
        response_payload=json.dumps(result.raw, ensure_ascii=False),
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def _adapter_error_result(provider_key: str, model_key: str, exc: AdapterError) -> UnifiedChatResult:
    return UnifiedChatResult(
        success=False,
        provider=provider_key,
        model=model_key,
        content="",
        usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "cached_tokens": 0},
        timing={"latency_ms": None, "ttft_ms": None},
        raw={"error_message": exc.message, "detail": exc.detail},
        http_status=exc.http_status,
        error=exc.code,
    )


def _run_summary(provider_key: str, model_key: str, run: ProbeRun) -> dict:
    return {
        "provider": provider_key,
        "model": model_key,
        "success": bool(run.success),
        "http_status": run.http_status,
        "latency_ms": run.latency_ms,
        "ttft_ms": run.ttft_ms,
        "cached_tokens": int(run.cached_tokens or 0),
        "tokens_per_sec": run.tokens_per_sec,
        "error_type": run.error_type,
        "error_message": run.error_message,
    }


def _delta(cold: float | None, warm: float | None) -> float | None:
    if cold is None or warm is None:
        return None
    return round(warm - cold, 2)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def since_24h() -> datetime:
    return utc_now() - timedelta(hours=24)
