import json
import math
from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.models import EvalResult, EvalSet, Model, ProbeRun, Provider
from app.services.providers import sync_provider_defaults_from_settings


def get_summary(db: Session) -> dict:
    sync_provider_defaults_from_settings(db)
    since = datetime.now(timezone.utc) - timedelta(hours=24)
    providers = db.scalars(select(Provider).where(Provider.enabled.is_(True)).order_by(Provider.id)).all()
    availability = []
    avg_ttft = []
    avg_tps = []
    latest_eval = []
    p95_ttft = []
    p95_latency = []
    avg_tpot = []
    goodput = []

    for provider in providers:
        perf_runs = _perf_runs(db, provider.id, None, since)
        total = db.scalar(
            select(func.count(ProbeRun.id)).where(
                and_(ProbeRun.provider_id == provider.id, ProbeRun.run_type == "health", ProbeRun.created_at >= since)
            )
        ) or 0
        success_count = db.scalar(
            select(func.count(ProbeRun.id)).where(
                and_(
                    ProbeRun.provider_id == provider.id,
                    ProbeRun.run_type == "health",
                    ProbeRun.success.is_(True),
                    ProbeRun.created_at >= since,
                )
            )
        ) or 0
        availability.append({"provider": provider.provider_key, "value": round(success_count / total, 4) if total else None})

        ttft = _average([run.ttft_ms for run in perf_runs if run.ttft_ms is not None])
        avg_ttft.append({"provider": provider.provider_key, "value": round(ttft, 2) if ttft is not None else None})

        tps = _average([run.tokens_per_sec for run in perf_runs if run.tokens_per_sec is not None])
        avg_tps.append({"provider": provider.provider_key, "value": round(tps, 2) if tps is not None else None})
        p95_ttft.append({"provider": provider.provider_key, "value": _percentile([run.ttft_ms for run in perf_runs if run.ttft_ms is not None], 0.95)})
        p95_latency.append({"provider": provider.provider_key, "value": _percentile([run.latency_ms for run in perf_runs if run.latency_ms is not None], 0.95)})
        avg_tpot.append({"provider": provider.provider_key, "value": _average_tpot(perf_runs)})
        goodput.append({"provider": provider.provider_key, "value": _goodput(perf_runs)})

        eval_row = db.execute(
            select(EvalResult.score)
            .join(EvalSet, EvalResult.eval_set_id == EvalSet.id)
            .where(and_(EvalSet.eval_key == "custom_eval", EvalResult.provider_id == provider.id))
            .order_by(EvalResult.created_at.desc())
            .limit(1)
        ).first()
        latest_eval.append({"provider": provider.provider_key, "score": round(eval_row[0], 4) if eval_row else None})

    return {
        "availability_24h": availability,
        "avg_ttft_24h": avg_ttft,
        "avg_tps_24h": avg_tps,
        "latest_custom_eval": latest_eval,
        "p95_ttft_24h": p95_ttft,
        "p95_latency_24h": p95_latency,
        "avg_tpot_24h": avg_tpot,
        "goodput_24h": goodput,
        "latest_benchmark_summary": _benchmark_summary(db),
    }


def get_compare(db: Session, providers: list[str], window: str) -> dict:
    sync_provider_defaults_from_settings(db)
    since = _parse_window(window)
    stmt = (
        select(Provider.provider_key, Model.model_key, Model.id, Provider.id)
        .join(Model, Model.provider_id == Provider.id)
        .where(Provider.enabled.is_(True), Model.enabled.is_(True))
    )
    if providers:
        stmt = stmt.where(Provider.provider_key.in_(providers))
    stmt = stmt.order_by(Provider.id, Model.id)
    rows = db.execute(stmt).all()
    items = []
    for provider_key, model_key, model_id, provider_id in rows:
        perf_runs = _perf_runs(db, provider_id, model_id, since)
        availability = _availability(db, provider_id, since)
        avg_latency = db.scalar(
            select(func.avg(ProbeRun.latency_ms)).where(
                and_(ProbeRun.provider_id == provider_id, ProbeRun.model_id == model_id, ProbeRun.created_at >= since)
            )
        )
        avg_ttft = db.scalar(
            select(func.avg(ProbeRun.ttft_ms)).where(
                and_(
                    ProbeRun.provider_id == provider_id,
                    ProbeRun.model_id == model_id,
                    ProbeRun.run_type == "perf",
                    ProbeRun.created_at >= since,
                )
            )
        )
        avg_tps = _average([run.tokens_per_sec for run in perf_runs if run.tokens_per_sec is not None])
        avg_cached = db.scalar(
            select(func.avg(ProbeRun.cached_tokens)).where(
                and_(
                    ProbeRun.provider_id == provider_id,
                    ProbeRun.model_id == model_id,
                    ProbeRun.run_type == "cache",
                    ProbeRun.created_at >= since,
                )
            )
        )
        latest_eval = db.execute(
            select(EvalResult.score)
            .join(EvalSet, EvalResult.eval_set_id == EvalSet.id)
            .where(
                and_(
                    EvalSet.eval_key == "custom_eval",
                    EvalResult.provider_id == provider_id,
                    EvalResult.model_id == model_id,
                )
            )
            .order_by(EvalResult.created_at.desc())
            .limit(1)
        ).first()
        items.append(
            {
                "provider": provider_key,
                "model": model_key,
                "availability": availability,
                "avg_latency_ms": round(avg_latency, 2) if avg_latency is not None else None,
                "avg_ttft_ms": round(avg_ttft, 2) if avg_ttft is not None else None,
                "avg_tps": round(avg_tps, 2) if avg_tps is not None else None,
                "p95_ttft_ms": _percentile([run.ttft_ms for run in perf_runs if run.ttft_ms is not None], 0.95),
                "p95_latency_ms": _percentile([run.latency_ms for run in perf_runs if run.latency_ms is not None], 0.95),
                "avg_tpot_ms": _average_tpot(perf_runs),
                "goodput": _goodput(perf_runs),
                "avg_cached_tokens": round(avg_cached, 2) if avg_cached is not None else None,
                "latest_eval_score": round(latest_eval[0], 4) if latest_eval else None,
            }
        )
    return {"window": window, "items": items}


def _availability(db: Session, provider_id: int, since: datetime) -> float | None:
    total = db.scalar(
        select(func.count(ProbeRun.id)).where(
            and_(ProbeRun.provider_id == provider_id, ProbeRun.run_type == "health", ProbeRun.created_at >= since)
        )
    ) or 0
    if total == 0:
        return None
    success = db.scalar(
        select(func.count(ProbeRun.id)).where(
            and_(
                ProbeRun.provider_id == provider_id,
                ProbeRun.run_type == "health",
                ProbeRun.success.is_(True),
                ProbeRun.created_at >= since,
            )
        )
    ) or 0
    return round(success / total, 4)


def _parse_window(window: str) -> datetime:
    now = datetime.now(timezone.utc)
    if window.endswith("h"):
        return now - timedelta(hours=int(window[:-1]))
    if window.endswith("d"):
        return now - timedelta(days=int(window[:-1]))
    return now - timedelta(hours=24)


def _perf_runs(db: Session, provider_id: int, model_id: int | None, since: datetime) -> list[ProbeRun]:
    stmt = select(ProbeRun).where(
        ProbeRun.provider_id == provider_id,
        ProbeRun.run_type == "perf",
        ProbeRun.created_at >= since,
    )
    if model_id is not None:
        stmt = stmt.where(ProbeRun.model_id == model_id)
    stmt = stmt.order_by(ProbeRun.created_at.desc())
    return db.scalars(stmt).all()


def _average(values: list[float | None]) -> float | None:
    numeric = [float(value) for value in values if value is not None]
    if not numeric:
        return None
    return sum(numeric) / len(numeric)


def _percentile(values: list[float | None], ratio: float) -> float | None:
    numeric = sorted(float(value) for value in values if value is not None)
    if not numeric:
        return None
    index = max(0, math.ceil(len(numeric) * ratio) - 1)
    return round(numeric[index], 2)


def _average_tpot(runs: list[ProbeRun]) -> float | None:
    values: list[float] = []
    for run in runs:
        if run.latency_ms is None or run.ttft_ms is None:
            continue
        completion_tokens = int(run.completion_tokens or 0)
        denominator = max(completion_tokens - 1, 1)
        values.append((run.latency_ms - run.ttft_ms) / denominator)
    if not values:
        return None
    return round(sum(values) / len(values), 2)


def _goodput(runs: list[ProbeRun]) -> float | None:
    if not runs:
        return None
    good = 0
    for run in runs:
        if not run.success:
            continue
        if run.ttft_ms is None or run.latency_ms is None:
            continue
        if run.ttft_ms > 1500 or run.latency_ms > 8000:
            continue
        if int(run.completion_tokens or 0) <= 0:
            continue
        if not _has_output(run.response_payload):
            continue
        good += 1
    return round(good / len(runs), 4)


def _has_output(response_payload: str | None) -> bool:
    if not response_payload:
        return False
    try:
        raw = json.loads(response_payload)
    except json.JSONDecodeError:
        return bool(response_payload.strip())

    if isinstance(raw, dict):
        if isinstance(raw.get("text"), str) and raw["text"].strip():
            return True
        if isinstance(raw.get("content"), str) and raw["content"].strip():
            return True
        choices = raw.get("choices") or []
        if choices:
            message = choices[0].get("message") or {}
            content = message.get("content")
            if isinstance(content, str) and content.strip():
                return True
            if isinstance(content, list):
                text = "".join(item.get("text", "") for item in content if isinstance(item, dict))
                if text.strip():
                    return True
        chunks = raw.get("chunks") or []
        chunk_text: list[str] = []
        for chunk in chunks:
            if not isinstance(chunk, dict):
                continue
            choices = chunk.get("choices") or []
            if not choices:
                continue
            delta = choices[0].get("delta") or {}
            content = delta.get("content")
            if isinstance(content, str):
                chunk_text.append(content)
        return bool("".join(chunk_text).strip())
    return False


def _benchmark_summary(db: Session) -> dict:
    stmt = (
        select(EvalResult, Provider.provider_key, Model.model_key)
        .join(EvalSet, EvalResult.eval_set_id == EvalSet.id)
        .join(Provider, EvalResult.provider_id == Provider.id)
        .join(Model, EvalResult.model_id == Model.id)
        .where(or_(EvalSet.source_type == "public", EvalSet.eval_key.like("benchmark%")))
        .order_by(EvalResult.created_at.desc())
    )
    latest_by_model: dict[tuple[str, str], dict] = {}
    for result, provider_key, model_key in db.execute(stmt).all():
        key = (provider_key, model_key)
        if key in latest_by_model:
            continue
        latest_by_model[key] = {
            "provider": provider_key,
            "model": model_key,
            "score": round(result.score, 4),
            "run_at": result.created_at,
        }

    items = sorted(latest_by_model.values(), key=lambda item: item["score"], reverse=True)
    if not items:
        return {"last_run_at": None, "best_model": None, "worst_model": None, "items": []}

    best = items[0]
    worst = min(items, key=lambda item: item["score"])
    last_run_at = max(item["run_at"] for item in items if item["run_at"] is not None)
    return {
        "last_run_at": last_run_at,
        "best_model": {"provider": best["provider"], "model": best["model"], "score": best["score"]},
        "worst_model": {"provider": worst["provider"], "model": worst["model"], "score": worst["score"]},
        "items": items,
    }
