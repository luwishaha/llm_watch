import os
import re
from pathlib import Path

from dotenv import dotenv_values
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_env: str = Field(default="prod", alias="APP_ENV")
    app_host: str = Field(default="0.0.0.0", alias="APP_HOST")
    app_port: int = Field(default=8000, alias="APP_PORT")
    database_url: str = Field(default="sqlite:///./data/llm_watch.db", alias="DATABASE_URL")

    deepseek_api_key: str = Field(default="", alias="DEEPSEEK_API_KEY")
    deepseek_base_url: str = Field(default="https://api.deepseek.com", alias="DEEPSEEK_BASE_URL")
    deepseek_model: str = Field(default="deepseek-chat", alias="DEEPSEEK_MODEL")

    dashscope_api_key: str = Field(default="", alias="DASHSCOPE_API_KEY")
    dashscope_base_url: str = Field(
        default="https://dashscope.aliyuncs.com/compatible-mode/v1",
        alias="DASHSCOPE_BASE_URL",
    )
    dashscope_model: str = Field(default="qwen-plus", alias="DASHSCOPE_MODEL")

    qianfan_api_key: str = Field(default="", alias="QIANFAN_API_KEY")
    qianfan_base_url: str = Field(default="https://qianfan.baidubce.com/v2", alias="QIANFAN_BASE_URL")
    qianfan_model: str = Field(default="ernie-4.0-turbo-128k", alias="QIANFAN_MODEL")

    scheduler_health_enabled: bool = Field(default=True, alias="SCHEDULER_HEALTH_ENABLED")
    scheduler_health_interval_minutes: int = Field(default=5, alias="SCHEDULER_HEALTH_INTERVAL_MINUTES")
    scheduler_perf_enabled: bool = Field(default=False, alias="SCHEDULER_PERF_ENABLED")
    scheduler_cache_enabled: bool = Field(default=False, alias="SCHEDULER_CACHE_ENABLED")
    scheduler_eval_enabled: bool = Field(default=False, alias="SCHEDULER_EVAL_ENABLED")

    request_timeout_seconds: float = Field(default=60.0, alias="REQUEST_TIMEOUT_SECONDS")
    provider_list: str = Field(default="deepseek,dashscope,qianfan", alias="LLM_WATCH_PROVIDERS")

    benchmark_dataset_path: str = Field(
        default=str(BASE_DIR / "datasets" / "benchmark_small.jsonl"),
        alias="BENCHMARK_DATASET_PATH",
    )
    custom_eval_dataset_path: str = Field(
        default=str(BASE_DIR / "datasets" / "custom_eval.jsonl"),
        alias="CUSTOM_EVAL_DATASET_PATH",
    )

    @property
    def env_map(self) -> dict[str, str]:
        file_values = {
            key: value
            for key, value in dotenv_values(BASE_DIR / ".env").items()
            if value is not None
        }
        merged = dict(file_values)
        merged.update(os.environ)
        return merged

    @property
    def provider_defaults(self) -> dict[str, dict[str, str | bool]]:
        builtin_defaults: dict[str, dict[str, str | bool]] = {
            "deepseek": {
                "api_key": self.deepseek_api_key,
                "base_url": self.deepseek_base_url,
                "model": self.deepseek_model,
                "api_key_env": "DEEPSEEK_API_KEY",
                "name": "DeepSeek",
                "enabled": True,
            },
            "dashscope": {
                "api_key": self.dashscope_api_key,
                "base_url": self.dashscope_base_url,
                "model": self.dashscope_model,
                "api_key_env": "DASHSCOPE_API_KEY",
                "name": "DashScope",
                "enabled": True,
            },
            "qianfan": {
                "api_key": self.qianfan_api_key,
                "base_url": self.qianfan_base_url,
                "model": self.qianfan_model,
                "api_key_env": "QIANFAN_API_KEY",
                "name": "Qianfan",
                "enabled": True,
            },
        }

        providers: dict[str, dict[str, str | bool]] = {}
        env_map = self.env_map
        for provider_key in self._discover_provider_keys(env_map):
            prefix = self._provider_env_prefix(provider_key)
            defaults = builtin_defaults.get(provider_key, {})
            base_url = str(env_map.get(f"{prefix}_BASE_URL") or defaults.get("base_url") or "").strip()
            model = str(env_map.get(f"{prefix}_MODEL") or defaults.get("model") or "").strip()
            if not base_url or not model:
                continue

            providers[provider_key] = {
                "api_key": str(env_map.get(f"{prefix}_API_KEY") or defaults.get("api_key") or ""),
                "base_url": base_url,
                "model": model,
                "api_key_env": f"{prefix}_API_KEY",
                "name": str(
                    env_map.get(f"{prefix}_NAME")
                    or defaults.get("name")
                    or provider_key.replace("-", " ").replace("_", " ").title()
                ).strip(),
                "enabled": self._parse_bool(env_map.get(f"{prefix}_ENABLED"), bool(defaults.get("enabled", True))),
            }
        return providers

    @property
    def provider_keys(self) -> list[str]:
        return [key for key, value in self.provider_defaults.items() if bool(value.get("enabled", True))]

    @property
    def resolved_database_url(self) -> str:
        if self.database_url.startswith("sqlite:///./"):
            relative_path = self.database_url.replace("sqlite:///./", "", 1)
            return f"sqlite:///{(BASE_DIR / relative_path).resolve().as_posix()}"
        return self.database_url

    def _discover_provider_keys(self, env_map: dict[str, str]) -> list[str]:
        keys: list[str] = []
        keys.extend(self._parse_provider_list(self.provider_list))
        for env_key in env_map:
            match = re.match(r"^([A-Z0-9_]+)_(API_KEY|BASE_URL|MODEL|NAME|ENABLED)$", env_key)
            if not match:
                continue
            provider_key = match.group(1).lower()
            if provider_key not in keys:
                keys.append(provider_key)
        return keys

    def _parse_provider_list(self, raw: str) -> list[str]:
        return [item.strip().lower() for item in raw.split(",") if item.strip()]

    def _provider_env_prefix(self, provider_key: str) -> str:
        return re.sub(r"[^A-Z0-9]+", "_", provider_key.upper())

    def _parse_bool(self, value: str | None, default: bool) -> bool:
        if value is None:
            return default
        return value.strip().lower() in {"1", "true", "yes", "on"}


def get_settings() -> Settings:
    return Settings()
