from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
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

    benchmark_dataset_path: str = Field(
        default=str(BASE_DIR / "datasets" / "benchmark_small.jsonl"),
        alias="BENCHMARK_DATASET_PATH",
    )
    custom_eval_dataset_path: str = Field(
        default=str(BASE_DIR / "datasets" / "custom_eval.jsonl"),
        alias="CUSTOM_EVAL_DATASET_PATH",
    )

    @property
    def provider_defaults(self) -> dict[str, dict[str, str]]:
        return {
            "deepseek": {
                "api_key": self.deepseek_api_key,
                "base_url": self.deepseek_base_url,
                "model": self.deepseek_model,
                "api_key_env": "DEEPSEEK_API_KEY",
                "name": "DeepSeek",
            },
            "dashscope": {
                "api_key": self.dashscope_api_key,
                "base_url": self.dashscope_base_url,
                "model": self.dashscope_model,
                "api_key_env": "DASHSCOPE_API_KEY",
                "name": "阿里百炼",
            },
            "qianfan": {
                "api_key": self.qianfan_api_key,
                "base_url": self.qianfan_base_url,
                "model": self.qianfan_model,
                "api_key_env": "QIANFAN_API_KEY",
                "name": "百度千帆",
            },
        }


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
