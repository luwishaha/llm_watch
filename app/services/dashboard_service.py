from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, func, select
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

    for provider in providers:
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

        ttft = db.scalar(
            select(func.avg(ProbeRun.ttft_ms)).where(
                and_(
                    ProbeRun.provider_id == provider.id,
                    ProbeRun.run_type == "perf",
                    ProbeRun.created_at >= since,
                )
            )
        )
        avg_ttft.append({"provider": provider.provider_key, "value": round(ttft, 2) if ttft is not None else None})

        tps = db.scalar(
            select(func.avg(ProbeRun.tokens_per_sec)).where(
                and_(
                    ProbeRun.provider_id == provider.id,
                    ProbeRun.run_type == "perf",
                    ProbeRun.created_at >= since,
                )
            )
        )
        avg_tps.append({"provider": provider.provider_key, "value": round(tps, 2) if tps is not None else None})

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
        avg_tps = db.scalar(
            select(func.avg(ProbeRun.tokens_per_sec)).where(
                and_(
                    ProbeRun.provider_id == provider_id,
                    ProbeRun.model_id == model_id,
                    ProbeRun.run_type == "perf",
                    ProbeRun.created_at >= since,
                )
            )
        )
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
