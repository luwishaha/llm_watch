import json
import re
from pathlib import Path
from typing import Any

from jsonschema import ValidationError, validate
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.adapters.base import AdapterError
from app.config import BASE_DIR
from app.models import EvalResult, EvalSet, Model, Provider
from app.services.providers import get_adapter, get_provider_and_model, list_enabled_provider_keys


UPLOADED_DATASETS_DIR = BASE_DIR / "datasets" / "uploaded"
EVAL_KEY_PATTERN = re.compile(r"^[a-z0-9_-]+$")


def load_eval_set(db: Session, eval_key: str) -> EvalSet:
    eval_set = db.scalars(select(EvalSet).where(EvalSet.eval_key == eval_key)).first()
    if eval_set is None:
        raise AdapterError(f"Unknown eval set '{eval_key}'.", code="unknown_eval_set")
    return eval_set


async def run_eval(db: Session, eval_key: str, providers: list[str]) -> list[dict]:
    eval_set = load_eval_set(db, eval_key)
    samples = _load_jsonl(_resolve_dataset_path(eval_set.dataset_path))
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


def list_eval_sets(db: Session) -> list[dict]:
    stmt = select(EvalSet).order_by(EvalSet.created_at.desc(), EvalSet.id.desc())
    return [_serialize_eval_set(row) for row in db.scalars(stmt).all()]


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


def import_eval_set_from_text(
    db: Session,
    eval_key: str,
    eval_name: str,
    source_type: str,
    content: str,
    enabled: bool,
) -> dict:
    normalized_key = normalize_eval_key(eval_key)
    eval_name = eval_name.strip()
    source_type = source_type.strip()
    if not eval_name:
        raise AdapterError("eval_name must not be empty.", code="invalid_eval_set")
    if not source_type:
        raise AdapterError("source_type must not be empty.", code="invalid_eval_set")

    samples = validate_jsonl_text(content)
    output_path = _dataset_output_path(normalized_key)
    dataset_path = _serialize_dataset_path(output_path)
    _write_dataset_text(output_path, content)
    status, row = upsert_eval_set(
        db,
        eval_key=normalized_key,
        eval_name=eval_name,
        source_type=source_type,
        dataset_path=dataset_path,
        enabled=enabled,
    )
    return {
        "status": status,
        "sample_count": len(samples),
        "item": _serialize_eval_set(row),
    }


def import_eval_set_from_upload(
    db: Session,
    eval_key: str,
    eval_name: str,
    source_type: str,
    filename: str,
    content_bytes: bytes,
    enabled: bool,
) -> dict:
    if not filename.lower().endswith(".jsonl"):
        raise AdapterError("Only .jsonl files are supported.", code="invalid_eval_set_file")
    try:
        content = content_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise AdapterError("Uploaded file must be valid UTF-8 JSONL.", code="invalid_dataset", detail=str(exc)) from exc
    return import_eval_set_from_text(db, eval_key, eval_name, source_type, content, enabled)


def validate_jsonl_text(content: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for idx, line in enumerate(content.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError as exc:
            raise AdapterError(
                f"Invalid JSONL at line {idx}.",
                code="invalid_dataset",
                detail=str(exc),
            ) from exc
        if not isinstance(item, dict):
            raise AdapterError(f"JSONL line {idx} must be a JSON object.", code="invalid_dataset")
        if not str(item.get("id", "")).strip():
            raise AdapterError(f"JSONL line {idx} is missing a non-empty 'id'.", code="invalid_dataset")
        if not str(item.get("prompt", "")).strip():
            raise AdapterError(f"JSONL line {idx} is missing a non-empty 'prompt'.", code="invalid_dataset")
        items.append(item)
    if not items:
        raise AdapterError("JSONL content is empty.", code="empty_eval_set")
    return items


def normalize_eval_key(eval_key: str) -> str:
    normalized = eval_key.strip()
    if not normalized or not EVAL_KEY_PATTERN.fullmatch(normalized):
        raise AdapterError(
            "eval_key must contain only lowercase letters, numbers, underscores, or hyphens.",
            code="invalid_eval_key",
        )
    return normalized


def upsert_eval_set(
    db: Session,
    eval_key: str,
    eval_name: str,
    source_type: str,
    dataset_path: str,
    enabled: bool,
) -> tuple[str, EvalSet]:
    row = db.scalars(select(EvalSet).where(EvalSet.eval_key == eval_key)).first()
    status = "updated" if row else "created"
    if row is None:
        row = EvalSet(
            eval_key=eval_key,
            eval_name=eval_name,
            source_type=source_type,
            dataset_path=dataset_path,
            enabled=enabled,
        )
        db.add(row)
    else:
        row.eval_name = eval_name
        row.source_type = source_type
        row.dataset_path = dataset_path
        row.enabled = enabled
    db.commit()
    db.refresh(row)
    return status, row


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise AdapterError(f"Dataset file '{path}' does not exist.", code="dataset_not_found")
    return validate_jsonl_text(path.read_text(encoding="utf-8"))


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


def _serialize_eval_set(row: EvalSet) -> dict[str, Any]:
    return {
        "eval_key": row.eval_key,
        "eval_name": row.eval_name,
        "source_type": row.source_type,
        "dataset_path": row.dataset_path,
        "enabled": bool(row.enabled),
        "created_at": row.created_at,
    }


def _dataset_relative_path(eval_key: str) -> str:
    return f"datasets/uploaded/{eval_key}.jsonl"


def _dataset_output_path(eval_key: str) -> Path:
    return UPLOADED_DATASETS_DIR / f"{eval_key}.jsonl"


def _resolve_dataset_path(dataset_path: str) -> Path:
    path = Path(dataset_path)
    if path.is_absolute():
        return path
    return BASE_DIR / path


def _write_dataset_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    normalized = content.replace("\r\n", "\n").strip()
    path.write_text(f"{normalized}\n", encoding="utf-8")


def _serialize_dataset_path(path: Path) -> str:
    try:
        return str(path.relative_to(BASE_DIR)).replace("\\", "/")
    except ValueError:
        return str(path)
