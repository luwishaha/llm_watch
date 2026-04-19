import json
import re
from pathlib import Path
from typing import Any

from jsonschema import ValidationError, validate
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.adapters.base import AdapterError
from app.models import EvalResult, EvalSet, Model, Provider
from app.services.providers import get_adapter, get_provider_and_model, list_enabled_provider_keys


def load_eval_set(db: Session, eval_key: str) -> EvalSet:
    eval_set = db.scalars(select(EvalSet).where(EvalSet.eval_key == eval_key)).first()
    if eval_set is None:
        raise AdapterError(f"Unknown eval set '{eval_key}'.", code="unknown_eval_set")
    return eval_set


async def run_eval(db: Session, eval_key: str, providers: list[str]) -> list[dict]:
    eval_set = load_eval_set(db, eval_key)
    samples = _load_jsonl(Path(eval_set.dataset_path))
    provider_keys = providers or list_enabled_provider_keys(db)
    results = []
    for provider_key in provider_keys:
        provider, model = get_provider_and_model(db, provider_key)
        adapter = get_adapter(provider_key)
        failures = []
        passed = 0
        for sample in samples:
            messages = [{"role": "user", "content": sample["prompt"]}]
            try:
                response = await adapter.chat(model.model_key, messages, stream=False, max_tokens=256, temperature=0)
                output = response.content.strip()
            except AdapterError as exc:
                failures.append(
                    {
                        "case_id": sample["id"],
                        "prompt": sample["prompt"],
                        "expected": sample.get("expected"),
                        "output": "",
                        "scoring": sample.get("scoring", "contains"),
                        "reason": exc.message,
                    }
                )
                continue

            ok, reason = _score_sample(sample, output)
            if ok:
                passed += 1
            else:
                failures.append(
                    {
                        "case_id": sample["id"],
                        "prompt": sample["prompt"],
                        "expected": sample.get("expected"),
                        "output": output,
                        "scoring": sample.get("scoring", "contains"),
                        "reason": reason,
                    }
                )

        total = len(samples)
        score = round((passed / total), 4) if total else 0.0
        detail = {
            "eval_set": eval_key,
            "passed": passed,
            "total": total,
            "failures": failures,
        }
        row = EvalResult(
            eval_set_id=eval_set.id,
            provider_id=provider.id,
            model_id=model.id,
            score=score,
            passed_count=passed,
            total_count=total,
            detail_json=json.dumps(detail, ensure_ascii=False),
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        results.append(
            {
                "provider": provider.provider_key,
                "model": model.model_key,
                "eval_set": eval_key,
                "score": score,
                "passed": passed,
                "total": total,
                "failures": failures,
            }
        )
    return results


def list_eval_results(
    db: Session,
    eval_set: str | None,
    provider: str | None,
    model: str | None,
    limit: int,
) -> list[dict]:
    stmt = (
        select(EvalResult, EvalSet.eval_key, Provider.provider_key, Model.model_key)
        .select_from(EvalResult)
        .join(EvalSet, EvalResult.eval_set_id == EvalSet.id)
        .join(Provider, EvalResult.provider_id == Provider.id)
        .join(Model, EvalResult.model_id == Model.id)
    )
    if eval_set:
        stmt = stmt.where(EvalSet.eval_key == eval_set)
    if provider:
        stmt = stmt.where(Provider.provider_key == provider)
    if model:
        stmt = stmt.where(Model.model_key == model)
    stmt = stmt.order_by(EvalResult.created_at.desc()).limit(limit)
    rows = db.execute(stmt).all()
    items = []
    for result, eval_key, provider_key, model_key in rows:
        detail = json.loads(result.detail_json) if result.detail_json else {}
        items.append(
            {
                "id": result.id,
                "eval_set": eval_key,
                "provider": provider_key,
                "model": model_key,
                "score": result.score,
                "passed": result.passed_count,
                "total": result.total_count,
                "failures": detail.get("failures", []),
                "created_at": result.created_at,
            }
        )
    return items


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise AdapterError(f"Dataset file '{path}' does not exist.", code="dataset_not_found")
    items = []
    for idx, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            items.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise AdapterError(
                f"Invalid JSONL at line {idx} in dataset '{path.name}'.",
                code="invalid_dataset",
                detail=str(exc),
            ) from exc
    return items


def _score_sample(sample: dict[str, Any], output: str) -> tuple[bool, str]:
    scoring = sample.get("scoring", "contains")
    expected = sample.get("expected", "")

    if scoring == "exact":
        return output.strip() == str(expected).strip(), "Output does not exactly match expected text."
    if scoring == "contains":
        return str(expected) in output, "Output does not contain expected text."
    if scoring == "regex":
        return re.search(str(expected), output) is not None, "Output does not match expected regex."
    if scoring == "json_schema":
        schema = sample.get("schema")
        if not schema:
            return False, "Sample missing schema."
        try:
            data = json.loads(output)
        except json.JSONDecodeError:
            return False, "Output is not valid JSON."
        try:
            validate(data, schema)
            return True, ""
        except ValidationError as exc:
            return False, f"JSON schema validation failed: {exc.message}"
    return False, f"Unsupported scoring type '{scoring}'."
