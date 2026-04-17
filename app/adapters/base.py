import json
import time
from dataclasses import dataclass
from typing import Any

import httpx

from app.config import get_settings


class AdapterError(Exception):
    def __init__(self, message: str, code: str = "adapter_error", http_status: int | None = None, detail: Any | None = None):
        super().__init__(message)
        self.message = message
        self.code = code
        self.http_status = http_status
        self.detail = detail


@dataclass
class UnifiedChatResult:
    success: bool
    provider: str
    model: str
    content: str
    usage: dict[str, int]
    timing: dict[str, float | None]
    raw: dict[str, Any]
    http_status: int | None = None
    error: str | None = None


class BaseProviderAdapter:
    provider_key: str = ""

    def __init__(self) -> None:
        self.settings = get_settings()
        cfg = self.settings.provider_defaults[self.provider_key]
        self.api_key = cfg["api_key"]
        self.base_url = cfg["base_url"].rstrip("/")
        self.default_model = cfg["model"]

    async def chat(self, model: str, messages: list[dict[str, Any]], stream: bool = False, **kwargs: Any) -> UnifiedChatResult:
        if not self.api_key:
            raise AdapterError(
                f"API key for provider '{self.provider_key}' is not configured.",
                code="missing_api_key",
                detail={"provider": self.provider_key},
            )

        payload = {
            "model": model or self.default_model,
            "messages": messages,
            "stream": stream,
        }
        if kwargs.get("max_tokens") is not None:
            payload["max_tokens"] = kwargs["max_tokens"]
        if kwargs.get("temperature") is not None:
            payload["temperature"] = kwargs["temperature"]
        if stream:
            payload["stream_options"] = {"include_usage": True}

        headers = self.build_headers()
        url = f"{self.base_url}/chat/completions"

        timeout = httpx.Timeout(self.settings.request_timeout_seconds)
        async with httpx.AsyncClient(timeout=timeout) as client:
            if stream:
                return await self._stream_chat(client, url, headers, payload)
            return await self._non_stream_chat(client, url, headers, payload)

    def build_headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    async def _non_stream_chat(
        self,
        client: httpx.AsyncClient,
        url: str,
        headers: dict[str, str],
        payload: dict[str, Any],
    ) -> UnifiedChatResult:
        start = time.perf_counter()
        try:
            response = await client.post(url, headers=headers, json=payload)
        except httpx.TimeoutException as exc:
            raise AdapterError("Provider request timed out.", code="provider_timeout") from exc
        except httpx.HTTPError as exc:
            raise AdapterError("Provider request failed.", code="provider_http_error", detail=str(exc)) from exc

        latency_ms = (time.perf_counter() - start) * 1000
        raw = self._parse_json_response(response)
        self._raise_for_error_status(response, raw)

        content = self.extract_content(raw)
        usage = self.extract_usage(raw)
        return UnifiedChatResult(
            success=True,
            provider=self.provider_key,
            model=payload["model"],
            content=content,
            usage=usage,
            timing={"latency_ms": round(latency_ms, 2), "ttft_ms": None},
            raw=raw,
            http_status=response.status_code,
        )

    async def _stream_chat(
        self,
        client: httpx.AsyncClient,
        url: str,
        headers: dict[str, str],
        payload: dict[str, Any],
    ) -> UnifiedChatResult:
        start = time.perf_counter()
        first_chunk_at: float | None = None
        content_parts: list[str] = []
        usage: dict[str, int] = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "cached_tokens": 0}
        raw_chunks: list[dict[str, Any]] = []
        http_status: int | None = None

        try:
            async with client.stream("POST", url, headers=headers, json=payload) as response:
                http_status = response.status_code
                if response.status_code >= 400:
                    raw = self._parse_json_response(response)
                    self._raise_for_error_status(response, raw)

                async for line in response.aiter_lines():
                    if not line or not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data)
                    except json.JSONDecodeError:
                        continue
                    raw_chunks.append(chunk)
                    delta = (((chunk.get("choices") or [{}])[0].get("delta") or {}).get("content")) or ""
                    if delta:
                        content_parts.append(delta)
                        if first_chunk_at is None:
                            first_chunk_at = time.perf_counter()
                    chunk_usage = self.extract_usage(chunk)
                    if chunk_usage["total_tokens"] > 0 or chunk_usage["cached_tokens"] > 0:
                        usage = chunk_usage
        except httpx.TimeoutException as exc:
            raise AdapterError("Provider request timed out.", code="provider_timeout") from exc
        except httpx.HTTPError as exc:
            raise AdapterError("Provider stream request failed.", code="provider_http_error", detail=str(exc)) from exc

        latency_ms = (time.perf_counter() - start) * 1000
        ttft_ms = ((first_chunk_at - start) * 1000) if first_chunk_at else None
        content = "".join(content_parts)
        if usage["completion_tokens"] == 0 and content:
            usage["completion_tokens"] = self.estimate_tokens(content)
            usage["total_tokens"] = usage["prompt_tokens"] + usage["completion_tokens"]

        return UnifiedChatResult(
            success=True,
            provider=self.provider_key,
            model=payload["model"],
            content=content,
            usage=usage,
            timing={"latency_ms": round(latency_ms, 2), "ttft_ms": round(ttft_ms, 2) if ttft_ms else None},
            raw={"chunks": raw_chunks},
            http_status=http_status,
        )

    def _parse_json_response(self, response: httpx.Response) -> dict[str, Any]:
        try:
            return response.json()
        except ValueError:
            return {"text": response.text}

    def _raise_for_error_status(self, response: httpx.Response, raw: dict[str, Any]) -> None:
        if response.status_code < 400:
            return
        message = raw.get("error", {}).get("message") if isinstance(raw.get("error"), dict) else None
        raise AdapterError(
            message or f"Provider returned HTTP {response.status_code}.",
            code="provider_bad_response",
            http_status=response.status_code,
            detail=raw,
        )

    def extract_content(self, raw: dict[str, Any]) -> str:
        choices = raw.get("choices") or []
        if not choices:
            return ""
        message = choices[0].get("message") or {}
        content = message.get("content", "")
        if isinstance(content, list):
            return "".join(item.get("text", "") for item in content if isinstance(item, dict))
        return str(content)

    def extract_usage(self, raw: dict[str, Any]) -> dict[str, int]:
        usage = raw.get("usage") or {}
        prompt_tokens_details = usage.get("prompt_tokens_details") or {}
        cached_tokens = usage.get("cached_tokens") or prompt_tokens_details.get("cached_tokens") or 0
        prompt_tokens = int(usage.get("prompt_tokens") or 0)
        completion_tokens = int(usage.get("completion_tokens") or 0)
        total_tokens = int(usage.get("total_tokens") or (prompt_tokens + completion_tokens))
        return {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "cached_tokens": int(cached_tokens or 0),
        }

    def estimate_tokens(self, text: str) -> int:
        chunks = text.split()
        if chunks:
            return len(chunks)
        return max(1, len(text) // 4) if text else 0
