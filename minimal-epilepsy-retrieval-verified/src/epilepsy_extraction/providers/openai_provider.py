from __future__ import annotations

import os
import time
from typing import Any

from .base import ProviderError, ProviderRequest, ProviderResponse, ProviderUsage, timed_response

# Models that do not accept an explicit temperature parameter.
_NO_TEMPERATURE_MODELS: frozenset[str] = frozenset({
    "gpt-5.5-2026-04-23",
})

_COST_PER_1K: dict[str, tuple[float, float]] = {
    "gpt-5.5-2026-04-23": (0.005, 0.015),
    "gpt-5.4-mini-2026-03-17": (0.0015, 0.006),
    "gpt-4o-2024-11-20": (0.0025, 0.010),
    "gpt-4o-mini-2024-07-18": (0.00015, 0.0006),
}


def _cost(model: str, input_tokens: int, output_tokens: int) -> float:
    rates = _COST_PER_1K.get(model)
    if rates is None:
        return 0.0
    return (input_tokens * rates[0] + output_tokens * rates[1]) / 1000.0


class OpenAIProvider:
    provider_name = "openai"

    def __init__(self, api_key: str | None = None) -> None:
        try:
            import openai as _openai
        except ImportError as exc:
            raise ImportError("Install openai: pip install openai") from exc
        self._client = _openai.OpenAI(api_key=api_key or os.environ["OPENAI_API_KEY"])

    def complete(self, request: ProviderRequest) -> ProviderResponse:
        messages = [{"role": m.role, "content": m.content} for m in request.messages]
        kwargs: dict[str, Any] = {
            "model": request.model,
            "messages": messages,
        }
        if request.model not in _NO_TEMPERATURE_MODELS:
            kwargs["temperature"] = request.temperature
        if request.response_format == "json":
            kwargs["response_format"] = {"type": "json_object"}

        started_at = time.perf_counter()
        try:
            resp = self._client.chat.completions.create(**kwargs)
        except Exception as exc:
            return timed_response(
                started_at,
                content="",
                model=request.model,
                provider=self.provider_name,
                error=ProviderError(type=type(exc).__name__, message=str(exc), retryable=False),
            )

        choice = resp.choices[0]
        content = choice.message.content or ""
        usage = resp.usage
        input_tokens = usage.prompt_tokens if usage else 0
        output_tokens = usage.completion_tokens if usage else 0
        return timed_response(
            started_at,
            content=content,
            model=resp.model,
            provider=self.provider_name,
            usage=ProviderUsage(
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost_usd=_cost(request.model, input_tokens, output_tokens),
            ),
            raw={"id": resp.id, "finish_reason": choice.finish_reason},
        )
