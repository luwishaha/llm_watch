from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class ErrorDetail(BaseModel):
    code: str
    message: str
    detail: Any | None = None


class ErrorResponse(BaseModel):
    success: Literal[False] = False
    error: ErrorDetail


class ChatMessage(BaseModel):
    role: str
    content: str


class UsageMetrics(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cached_tokens: int = 0


class TimingMetrics(BaseModel):
    latency_ms: float | None = None
    ttft_ms: float | None = None


class ChatResponse(BaseModel):
    success: bool = True
    provider: str
    model: str
    content: str
    usage: UsageMetrics
    timing: TimingMetrics
    http_status: int | None = None
    raw: dict[str, Any] | None = None


class HealthResponse(BaseModel):
    success: bool = True
    service: str
    time: datetime


class ProviderModelInfo(BaseModel):
    provider: str
    provider_name: str
    base_url: str
    default_model: str
    models: list[str]
    enabled: bool
    api_key_configured: bool
    api_key_env: str


class ProvidersResponse(BaseModel):
    success: bool = True
    items: list[ProviderModelInfo]


class ProviderTestRequest(BaseModel):
    provider: str
    model: str | None = None


class ChatRequest(BaseModel):
    provider: str
    model: str | None = None
    messages: list[ChatMessage]
    stream: bool = False
    max_tokens: int | None = 128
    temperature: float | None = 0.2


class ProbeRunRequest(BaseModel):
    providers: list[str] = Field(default_factory=list)


class PerfProbeRunRequest(ProbeRunRequest):
    prompt_template: str = "standard_short"
    max_tokens: int = 128


class CacheProbeRunRequest(ProbeRunRequest):
    prompt_template: str = "long_prefix_cache"


class ProbeRunItem(BaseModel):
    id: int
    provider: str
    model: str
    run_type: str
    success: bool
    http_status: int | None = None
    latency_ms: float | None = None
    ttft_ms: float | None = None
    cached_tokens: int | None = None
    tokens_per_sec: float | None = None
    error_type: str | None = None
    error_message: str | None = None
    created_at: datetime


class ProbeRunSummary(BaseModel):
    provider: str
    model: str
    success: bool
    http_status: int | None = None
    latency_ms: float | None = None
    ttft_ms: float | None = None
    cached_tokens: int = 0
    tokens_per_sec: float | None = None
    error_type: str | None = None
    error_message: str | None = None


class CacheProbeSummary(BaseModel):
    provider: str
    model: str
    cold: ProbeRunSummary
    warm: ProbeRunSummary
    delta_latency_ms: float | None = None
    delta_ttft_ms: float | None = None
    cached_tokens: int = 0


class ProbeRunResponse(BaseModel):
    success: bool = True
    run_type: str
    results: list[ProbeRunSummary | CacheProbeSummary]


class ProbeRunsResponse(BaseModel):
    success: bool = True
    items: list[ProbeRunItem]


class EvalRunRequest(BaseModel):
    eval_set: str
    providers: list[str] = Field(default_factory=list)

    @field_validator("eval_set")
    @classmethod
    def validate_eval_set(cls, value: str) -> str:
        eval_set = value.strip()
        if not eval_set:
            raise ValueError("eval_set must not be empty.")
        return eval_set


class EvalFailureItem(BaseModel):
    case_id: str
    prompt: str
    expected: Any | None = None
    output: str
    scoring: str
    reason: str


class EvalResultItem(BaseModel):
    id: int
    eval_set: str
    provider: str
    model: str
    score: float
    passed: int
    total: int
    failures: list[EvalFailureItem] = Field(default_factory=list)
    created_at: datetime


class EvalRunSummary(BaseModel):
    provider: str
    model: str
    eval_set: str
    score: float
    passed: int
    total: int
    failures: list[EvalFailureItem] = Field(default_factory=list)


class EvalRunResponse(BaseModel):
    success: bool = True
    eval_set: str
    results: list[EvalRunSummary]


class EvalResultsResponse(BaseModel):
    success: bool = True
    items: list[EvalResultItem]


class EvalSetItem(BaseModel):
    eval_key: str
    eval_name: str
    source_type: str
    dataset_path: str
    enabled: bool
    created_at: datetime


class EvalSetImportRequest(BaseModel):
    eval_key: str
    eval_name: str
    source_type: str
    content: str
    enabled: bool = True


class EvalSetListResponse(BaseModel):
    success: bool = True
    items: list[EvalSetItem]


class EvalSetImportResponse(BaseModel):
    success: bool = True
    status: str
    sample_count: int
    item: EvalSetItem


class MetricPoint(BaseModel):
    provider: str
    value: float | None = None
    score: float | None = None


class BenchmarkSummaryItem(BaseModel):
    provider: str
    model: str
    score: float
    run_at: datetime | None = None


class BenchmarkModelSummary(BaseModel):
    provider: str
    model: str
    score: float


class BenchmarkSummaryData(BaseModel):
    last_run_at: datetime | None = None
    best_model: BenchmarkModelSummary | None = None
    worst_model: BenchmarkModelSummary | None = None
    items: list[BenchmarkSummaryItem] = Field(default_factory=list)


class DashboardSummaryData(BaseModel):
    availability_24h: list[MetricPoint]
    avg_ttft_24h: list[MetricPoint]
    avg_tps_24h: list[MetricPoint]
    latest_custom_eval: list[MetricPoint]
    p95_ttft_24h: list[MetricPoint]
    p95_latency_24h: list[MetricPoint]
    avg_tpot_24h: list[MetricPoint]
    goodput_24h: list[MetricPoint]
    latest_benchmark_summary: BenchmarkSummaryData


class DashboardSummaryResponse(BaseModel):
    success: bool = True
    summary: DashboardSummaryData


class CompareTableRow(BaseModel):
    provider: str
    model: str
    availability: float | None = None
    avg_latency_ms: float | None = None
    avg_ttft_ms: float | None = None
    p95_ttft_ms: float | None = None
    p95_latency_ms: float | None = None
    avg_tps: float | None = None
    avg_tpot_ms: float | None = None
    goodput: float | None = None
    avg_cached_tokens: float | None = None
    latest_eval_score: float | None = None


class DashboardCompareData(BaseModel):
    window: str
    items: list[CompareTableRow]


class DashboardCompareResponse(BaseModel):
    success: bool = True
    compare: DashboardCompareData
