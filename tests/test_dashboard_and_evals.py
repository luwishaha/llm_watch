import json
import shutil
import unittest
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.adapters.base import AdapterError
from app.db import Base, get_db
from app.main import adapter_error_handler, generic_error_handler
from app.models import EvalResult, EvalSet, Model, ProbeRun, Provider
from app.routers import evals
from app.services import dashboard_service, eval_service


def create_test_session() -> tuple[Session, Path]:
    tmp_root = Path("tests/.tmp")
    tmp_root.mkdir(parents=True, exist_ok=True)
    tmpdir = tmp_root / f"llm_watch_test_{uuid.uuid4().hex}"
    tmpdir.mkdir(parents=True, exist_ok=True)
    db_path = tmpdir / "test.db"
    engine = create_engine(f"sqlite:///{db_path.resolve().as_posix()}", future=True)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    return SessionLocal(), tmpdir


class DashboardServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.db, self.tmpdir = create_test_session()
        now = datetime.now(timezone.utc)

        deepseek = Provider(
            provider_key="deepseek",
            provider_name="DeepSeek",
            base_url="https://example.com/deepseek",
            api_key_env="DEEPSEEK_API_KEY",
            enabled=True,
        )
        dashscope = Provider(
            provider_key="dashscope",
            provider_name="DashScope",
            base_url="https://example.com/dashscope",
            api_key_env="DASHSCOPE_API_KEY",
            enabled=True,
        )
        self.db.add_all([deepseek, dashscope])
        self.db.flush()

        deepseek_model = Model(provider_id=deepseek.id, model_key="deepseek-chat", model_name="deepseek-chat", enabled=True)
        dashscope_model = Model(provider_id=dashscope.id, model_key="qwen-plus", model_name="qwen-plus", enabled=True)
        self.db.add_all([deepseek_model, dashscope_model])
        self.db.flush()

        benchmark_set = EvalSet(
            eval_key="benchmark_small",
            eval_name="Benchmark Small",
            source_type="public",
            dataset_path="datasets/benchmark_small.jsonl",
            enabled=True,
        )
        custom_set = EvalSet(
            eval_key="custom_eval",
            eval_name="Custom Eval",
            source_type="custom",
            dataset_path="datasets/custom_eval.jsonl",
            enabled=True,
        )
        self.db.add_all([benchmark_set, custom_set])
        self.db.flush()

        health_runs = [
            ProbeRun(
                provider_id=deepseek.id,
                model_id=deepseek_model.id,
                run_type="health",
                success=True,
                latency_ms=100,
                ttft_ms=None,
                response_payload=json.dumps({"text": "ok"}),
                created_at=now - timedelta(hours=1),
            ),
            ProbeRun(
                provider_id=deepseek.id,
                model_id=deepseek_model.id,
                run_type="health",
                success=False,
                latency_ms=120,
                ttft_ms=None,
                response_payload=json.dumps({"text": ""}),
                created_at=now - timedelta(hours=2),
            ),
            ProbeRun(
                provider_id=dashscope.id,
                model_id=dashscope_model.id,
                run_type="health",
                success=True,
                latency_ms=90,
                ttft_ms=None,
                response_payload=json.dumps({"text": "ok"}),
                created_at=now - timedelta(hours=1),
            ),
        ]

        perf_runs = [
            ProbeRun(
                provider_id=deepseek.id,
                model_id=deepseek_model.id,
                run_type="perf",
                success=True,
                latency_ms=1000,
                ttft_ms=100,
                completion_tokens=11,
                total_tokens=21,
                tokens_per_sec=11.0,
                response_payload=json.dumps({"chunks": [{"choices": [{"delta": {"content": "hello"}}]}]}),
                created_at=now - timedelta(minutes=30),
            ),
            ProbeRun(
                provider_id=deepseek.id,
                model_id=deepseek_model.id,
                run_type="perf",
                success=True,
                latency_ms=3000,
                ttft_ms=200,
                completion_tokens=21,
                total_tokens=31,
                tokens_per_sec=8.0,
                response_payload=json.dumps({"text": "world"}),
                created_at=now - timedelta(minutes=25),
            ),
            ProbeRun(
                provider_id=deepseek.id,
                model_id=deepseek_model.id,
                run_type="perf",
                success=False,
                latency_ms=9000,
                ttft_ms=300,
                completion_tokens=0,
                total_tokens=10,
                tokens_per_sec=0.0,
                response_payload=json.dumps({"text": ""}),
                created_at=now - timedelta(minutes=20),
            ),
            ProbeRun(
                provider_id=dashscope.id,
                model_id=dashscope_model.id,
                run_type="perf",
                success=True,
                latency_ms=800,
                ttft_ms=80,
                completion_tokens=9,
                total_tokens=19,
                tokens_per_sec=12.0,
                response_payload=json.dumps({"text": "ok"}),
                created_at=now - timedelta(minutes=15),
            ),
        ]

        eval_results = [
            EvalResult(
                eval_set_id=benchmark_set.id,
                provider_id=deepseek.id,
                model_id=deepseek_model.id,
                score=0.62,
                passed_count=5,
                total_count=8,
                detail_json="{}",
                created_at=now - timedelta(minutes=10),
            ),
            EvalResult(
                eval_set_id=benchmark_set.id,
                provider_id=dashscope.id,
                model_id=dashscope_model.id,
                score=0.81,
                passed_count=7,
                total_count=8,
                detail_json="{}",
                created_at=now - timedelta(minutes=5),
            ),
            EvalResult(
                eval_set_id=custom_set.id,
                provider_id=deepseek.id,
                model_id=deepseek_model.id,
                score=0.55,
                passed_count=4,
                total_count=8,
                detail_json="{}",
                created_at=now - timedelta(minutes=8),
            ),
            EvalResult(
                eval_set_id=custom_set.id,
                provider_id=dashscope.id,
                model_id=dashscope_model.id,
                score=0.9,
                passed_count=7,
                total_count=8,
                detail_json="{}",
                created_at=now - timedelta(minutes=3),
            ),
        ]

        self.db.add_all(health_runs + perf_runs + eval_results)
        self.db.commit()

    def tearDown(self) -> None:
        self.db.close()
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_summary_includes_new_metric_groups_and_benchmark_summary(self) -> None:
        with patch.object(dashboard_service, "sync_provider_defaults_from_settings", lambda db: None):
            summary = dashboard_service.get_summary(self.db)

        self.assertIn("p95_ttft_24h", summary)
        self.assertIn("p95_latency_24h", summary)
        self.assertIn("avg_tpot_24h", summary)
        self.assertIn("goodput_24h", summary)
        self.assertIn("latest_benchmark_summary", summary)

        p95_ttft = {item["provider"]: item["value"] for item in summary["p95_ttft_24h"]}
        p95_latency = {item["provider"]: item["value"] for item in summary["p95_latency_24h"]}
        avg_tpot = {item["provider"]: item["value"] for item in summary["avg_tpot_24h"]}
        goodput = {item["provider"]: item["value"] for item in summary["goodput_24h"]}

        self.assertEqual(300.0, p95_ttft["deepseek"])
        self.assertEqual(80.0, p95_ttft["dashscope"])
        self.assertEqual(9000.0, p95_latency["deepseek"])
        self.assertEqual(800.0, p95_latency["dashscope"])
        self.assertEqual(2976.67, avg_tpot["deepseek"])
        self.assertEqual(90.0, avg_tpot["dashscope"])
        self.assertEqual(round(2 / 3, 4), goodput["deepseek"])
        self.assertEqual(1.0, goodput["dashscope"])

        benchmark_summary = summary["latest_benchmark_summary"]
        self.assertEqual(2, len(benchmark_summary["items"]))
        self.assertEqual("dashscope", benchmark_summary["best_model"]["provider"])
        self.assertEqual("deepseek", benchmark_summary["worst_model"]["provider"])
        self.assertIsNotNone(benchmark_summary["last_run_at"])

    def test_compare_includes_new_metrics(self) -> None:
        with patch.object(dashboard_service, "sync_provider_defaults_from_settings", lambda db: None):
            compare = dashboard_service.get_compare(self.db, ["deepseek", "dashscope"], "24h")

        deepseek_row = next(item for item in compare["items"] if item["provider"] == "deepseek")
        self.assertEqual(300.0, deepseek_row["p95_ttft_ms"])
        self.assertEqual(9000.0, deepseek_row["p95_latency_ms"])
        self.assertEqual(2976.67, deepseek_row["avg_tpot_ms"])
        self.assertEqual(round(2 / 3, 4), deepseek_row["goodput"])


class EvalApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.db, self.tmpdir = create_test_session()
        provider = Provider(
            provider_key="deepseek",
            provider_name="DeepSeek",
            base_url="https://example.com/deepseek",
            api_key_env="DEEPSEEK_API_KEY",
            enabled=True,
        )
        self.db.add(provider)
        self.db.flush()

        model = Model(provider_id=provider.id, model_key="deepseek-chat", model_name="deepseek-chat", enabled=True)
        builtin_eval = EvalSet(
            eval_key="benchmark_small",
            eval_name="Benchmark Small",
            source_type="public",
            dataset_path="datasets/benchmark_small.jsonl",
            enabled=True,
        )
        self.db.add_all([model, builtin_eval])
        self.db.commit()

        app = FastAPI()
        app.include_router(evals.router)
        app.add_exception_handler(AdapterError, adapter_error_handler)
        app.add_exception_handler(Exception, generic_error_handler)

        def override_get_db():
            try:
                yield self.db
            finally:
                pass

        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)

    def tearDown(self) -> None:
        self.db.close()
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_list_eval_sets_endpoint_returns_rows(self) -> None:
        response = self.client.get("/api/eval-sets")

        self.assertEqual(200, response.status_code)
        payload = response.json()
        self.assertTrue(payload["success"])
        self.assertEqual("benchmark_small", payload["items"][0]["eval_key"])

    def test_import_text_endpoint_accepts_valid_jsonl_and_persists_file(self) -> None:
        with patch.object(eval_service, "UPLOADED_DATASETS_DIR", self.tmpdir / "uploaded"):
            response = self.client.post(
                "/api/eval-sets/import-text",
                json={
                    "eval_key": "demo_set",
                    "eval_name": "Demo Set",
                    "source_type": "custom",
                    "content": '{"id":"1","prompt":"hi","expected":"hello","scoring":"contains"}',
                    "enabled": True,
                },
            )

        self.assertEqual(200, response.status_code)
        payload = response.json()
        self.assertEqual("demo_set", payload["item"]["eval_key"])
        self.assertTrue((self.tmpdir / "uploaded" / "demo_set.jsonl").exists())

    def test_upload_endpoint_rejects_non_jsonl_files_with_unified_error_shape(self) -> None:
        response = self.client.post(
            "/api/eval-sets/upload",
            files={"file": ("bad.txt", b"plain text", "text/plain")},
            data={
                "eval_key": "bad_set",
                "eval_name": "Bad Set",
                "source_type": "custom",
                "enabled": "true",
            },
        )

        self.assertEqual(400, response.status_code)
        payload = response.json()
        self.assertFalse(payload["success"])
        self.assertEqual("invalid_eval_set_file", payload["error"]["code"])

    def test_eval_run_endpoint_accepts_imported_eval_key(self) -> None:
        async def fake_run_eval(db, eval_key, providers):
            return [{"provider": "deepseek", "model": "deepseek-chat", "eval_set": eval_key, "score": 1.0, "passed": 1, "total": 1, "failures": []}]

        with patch.object(evals.eval_service, "run_eval", side_effect=fake_run_eval):
            response = self.client.post(
                "/api/evals/run",
                json={"eval_set": "demo_set", "providers": ["deepseek"]},
            )

        self.assertEqual(200, response.status_code)
        self.assertEqual("demo_set", response.json()["eval_set"])

    def test_import_service_updates_existing_eval_key(self) -> None:
        with patch.object(eval_service, "UPLOADED_DATASETS_DIR", self.tmpdir / "uploaded"):
            created = eval_service.import_eval_set_from_text(
                self.db,
                eval_key="update_me",
                eval_name="Update Me",
                source_type="custom",
                content='{"id":"1","prompt":"A","expected":"B","scoring":"contains"}',
                enabled=True,
            )
            updated = eval_service.import_eval_set_from_text(
                self.db,
                eval_key="update_me",
                eval_name="Updated Name",
                source_type="public",
                content='{"id":"2","prompt":"C","expected":"D","scoring":"contains"}',
                enabled=False,
            )

        self.assertEqual("created", created["status"])
        self.assertEqual("updated", updated["status"])
        row = self.db.query(EvalSet).filter(EvalSet.eval_key == "update_me").one()
        self.assertEqual("Updated Name", row.eval_name)
        self.assertEqual("public", row.source_type)
        self.assertFalse(row.enabled)


if __name__ == "__main__":
    unittest.main()
