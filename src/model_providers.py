#!/usr/bin/env python3
"""Provider-neutral request, response, and adapter layer for model experiments."""

from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from direct_baselines import load_dotenv
from model_registry import ModelSpec


@dataclass
class ModelRequest:
    prompt: str
    model: ModelSpec
    harness_id: str
    temperature: float = 0.0
    max_output_tokens: int | None = None
    schema_mode: str | None = None
    response_json_schema: dict[str, Any] | None = None
    seed: int | None = None
    reasoning_effort: str | None = None
    google_thinking_budget: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class TokenUsage:
    input_tokens: int | None = None
    output_tokens: int | None = None
    cache_read_tokens: int | None = None
    cache_write_tokens: int | None = None


@dataclass
class ModelResponse:
    provider: str
    model_label: str
    model_id: str
    harness_id: str
    schema_mode: str | None
    text: str
    parsed: Any | None
    token_usage: TokenUsage
    latency_ms: float
    stop_reason: str | None
    retries: int
    provider_metadata: dict[str, Any]
    raw_response_path: str | None
    estimated_cost: dict[str, Any]
    request_metadata: dict[str, Any]
    error: str | None = None


class ProviderAdapter:
    provider = "base"

    def call(self, request: ModelRequest) -> ModelResponse:
        raise NotImplementedError

    def _response(
        self,
        request: ModelRequest,
        text: str,
        started: float,
        usage: TokenUsage | None = None,
        stop_reason: str | None = None,
        provider_metadata: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> ModelResponse:
        return ModelResponse(
            provider=self.provider,
            model_label=request.model.label,
            model_id=request.model.provider_model_id,
            harness_id=request.harness_id,
            schema_mode=request.schema_mode,
            text=text,
            parsed=None,
            token_usage=usage or TokenUsage(),
            latency_ms=(time.perf_counter() - started) * 1000,
            stop_reason=stop_reason,
            retries=0,
            provider_metadata=provider_metadata or {},
            raw_response_path=None,
            estimated_cost=estimate_cost(request.model, usage or TokenUsage()),
            request_metadata=request.metadata,
            error=error,
        )


class StubAdapter(ProviderAdapter):
    provider = "stub"

    def call(self, request: ModelRequest) -> ModelResponse:
        started = time.perf_counter()
        payload = {
            "provider": "stub",
            "model_label": request.model.label,
            "model_id": request.model.provider_model_id,
            "harness_id": request.harness_id,
            "status": "stubbed_no_provider_call",
        }
        return self._response(
            request,
            json.dumps(payload, indent=2),
            started,
            usage=TokenUsage(input_tokens=0, output_tokens=0),
            stop_reason="stub",
            provider_metadata={"stub": True},
        )


class OpenAIAdapter(ProviderAdapter):
    provider = "openai"

    def call(self, request: ModelRequest) -> ModelResponse:
        load_dotenv()
        started = time.perf_counter()
        if not os.environ.get("OPENAI_API_KEY"):
            return self._response(request, "", started, error="OPENAI_API_KEY is not set")
        try:
            from openai import OpenAI
        except ImportError as exc:
            return self._response(request, "", started, error=f"openai is not installed: {exc}")

        try:
            client = OpenAI()
            kwargs: dict[str, Any] = {
                "model": request.model.provider_model_id,
                "input": request.prompt,
            }
            if request.temperature is not None:
                kwargs["temperature"] = request.temperature
            if request.max_output_tokens:
                kwargs["max_output_tokens"] = request.max_output_tokens
            if request.reasoning_effort:
                kwargs["reasoning"] = {"effort": request.reasoning_effort}
            if request.response_json_schema:
                kwargs["text"] = {
                    "format": {
                        "type": "json_schema",
                        "name": request.response_json_schema.get("name", "structured_response"),
                        "schema": request.response_json_schema["schema"],
                        "strict": request.response_json_schema.get("strict", True),
                    }
                }
            retries = 0
            _droppable = [("reasoning", "reasoning"), ("temperature", "temperature")]
            while True:
                try:
                    response = client.responses.create(**kwargs)
                    break
                except Exception as exc:
                    exc_str = str(exc)
                    dropped = False
                    for signal, param in _droppable:
                        if signal in exc_str and param in kwargs:
                            kwargs.pop(param)
                            retries += 1
                            dropped = True
                            break
                    if not dropped:
                        raise
            usage = getattr(response, "usage", None)
            token_usage = TokenUsage(
                input_tokens=getattr(usage, "input_tokens", None),
                output_tokens=getattr(usage, "output_tokens", None),
            )
            metadata = response.model_dump(mode="json", exclude={"output"}, exclude_none=True)
            model_response = self._response(
                request,
                getattr(response, "output_text", "") or "",
                started,
                usage=token_usage,
                stop_reason=getattr(response, "status", None),
                provider_metadata=metadata,
            )
            model_response.retries = retries
            return model_response
        except Exception as exc:
            return self._response(request, "", started, error=str(exc))


class AnthropicAdapter(ProviderAdapter):
    provider = "anthropic"

    def call(self, request: ModelRequest) -> ModelResponse:
        load_dotenv()
        started = time.perf_counter()
        if not os.environ.get("ANTHROPIC_API_KEY"):
            return self._response(request, "", started, error="ANTHROPIC_API_KEY is not set")
        try:
            from anthropic import Anthropic
        except ImportError as exc:
            return self._response(request, "", started, error=f"anthropic is not installed: {exc}")

        try:
            client = Anthropic()
            response = client.messages.create(
                model=request.model.provider_model_id,
                max_tokens=request.max_output_tokens or request.model.max_output_tokens or 4096,
                temperature=request.temperature,
                messages=[{"role": "user", "content": request.prompt}],
            )
            text = "\n".join(block.text for block in response.content if getattr(block, "type", None) == "text")
            usage = getattr(response, "usage", None)
            token_usage = TokenUsage(
                input_tokens=getattr(usage, "input_tokens", None),
                output_tokens=getattr(usage, "output_tokens", None),
                cache_read_tokens=getattr(usage, "cache_read_input_tokens", None),
                cache_write_tokens=getattr(usage, "cache_creation_input_tokens", None),
            )
            metadata = response.model_dump(mode="json", exclude={"content"}, exclude_none=True)
            return self._response(
                request,
                text,
                started,
                usage=token_usage,
                stop_reason=getattr(response, "stop_reason", None),
                provider_metadata=metadata,
            )
        except Exception as exc:
            return self._response(request, "", started, error=str(exc))


class GoogleAdapter(ProviderAdapter):
    provider = "google"

    def call(self, request: ModelRequest) -> ModelResponse:
        load_dotenv()
        started = time.perf_counter()
        if not (os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")):
            return self._response(request, "", started, error="GOOGLE_API_KEY or GEMINI_API_KEY is not set")
        try:
            from google import genai
            from google.genai import types
        except ImportError as exc:
            return self._response(request, "", started, error=f"google-genai is not installed: {exc}")

        try:
            api_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
            client = genai.Client(api_key=api_key)
            config = types.GenerateContentConfig(
                temperature=request.temperature,
                max_output_tokens=request.max_output_tokens or request.model.max_output_tokens,
            )
            if request.google_thinking_budget is not None:
                config.thinking_config = types.ThinkingConfig(thinking_budget=request.google_thinking_budget)
            response = client.models.generate_content(
                model=request.model.provider_model_id,
                contents=request.prompt,
                config=config,
            )
            usage = getattr(response, "usage_metadata", None)
            token_usage = TokenUsage(
                input_tokens=getattr(usage, "prompt_token_count", None),
                output_tokens=getattr(usage, "candidates_token_count", None),
            )
            metadata = response.model_dump(mode="json", exclude={"candidates"}, exclude_none=True)
            return self._response(
                request,
                getattr(response, "text", "") or "",
                started,
                usage=token_usage,
                stop_reason=None,
                provider_metadata=metadata,
            )
        except Exception as exc:
            return self._response(request, "", started, error=str(exc))


def adapter_for(provider: str) -> ProviderAdapter:
    adapters: dict[str, ProviderAdapter] = {
        "stub": StubAdapter(),
        "openai": OpenAIAdapter(),
        "anthropic": AnthropicAdapter(),
        "google": GoogleAdapter(),
    }
    if provider not in adapters:
        raise ValueError(f"unsupported provider: {provider}")
    return adapters[provider]


def estimate_cost(model: ModelSpec, usage: TokenUsage) -> dict[str, Any]:
    def component(tokens: int | None, price: float | None) -> float | None:
        if tokens is None or price is None:
            return None
        return (tokens / 1_000_000) * price

    parts = {
        "input": component(usage.input_tokens, model.pricing["input_per_million"]),
        "output": component(usage.output_tokens, model.pricing["output_per_million"]),
        "cache_read": component(usage.cache_read_tokens, model.pricing["cache_read_per_million"]),
        "cache_write": component(usage.cache_write_tokens, model.pricing["cache_write_per_million"]),
    }
    known_parts = [value for value in parts.values() if value is not None]
    missing_required = []
    if usage.input_tokens is None or model.pricing["input_per_million"] is None:
        missing_required.append("input")
    if usage.output_tokens is None or model.pricing["output_per_million"] is None:
        missing_required.append("output")
    if usage.cache_read_tokens is not None and model.pricing["cache_read_per_million"] is None:
        missing_required.append("cache_read")
    if usage.cache_write_tokens is not None and model.pricing["cache_write_per_million"] is None:
        missing_required.append("cache_write")
    return {
        "currency": model.billing_currency,
        "pricing_snapshot_date": model.pricing_snapshot_date,
        "components": parts,
        "total": sum(known_parts) if not missing_required else None,
        "status": "complete" if not missing_required else "missing_price_or_usage",
        "missing_required": missing_required,
    }


def write_response_log(response: ModelResponse, path: Path) -> None:
    record = asdict(response)
    record["logged_at"] = datetime.now(timezone.utc).isoformat()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
