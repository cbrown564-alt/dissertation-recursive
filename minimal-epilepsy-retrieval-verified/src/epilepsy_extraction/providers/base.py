from __future__ import annotations

import time
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any, Protocol

from epilepsy_extraction.schemas import BudgetMetadata


@dataclass(frozen=True)
class ProviderMessage:
    role: str
    content: str


@dataclass(frozen=True)
class ProviderRequest:
    messages: list[ProviderMessage]
    model: str
    temperature: float = 0.0
    response_format: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ProviderUsage:
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


@dataclass(frozen=True)
class ProviderError:
    type: str
    message: str
    retryable: bool = False


@dataclass(frozen=True)
class ProviderResponse:
    content: str
    model: str
    provider: str
    usage: ProviderUsage = field(default_factory=ProviderUsage)
    latency_ms: int = 0
    raw: Mapping[str, Any] = field(default_factory=dict)
    error: ProviderError | None = None

    @property
    def ok(self) -> bool:
        return self.error is None


class ChatProvider(Protocol):
    provider_name: str

    def complete(self, request: ProviderRequest) -> ProviderResponse:
        ...


def timed_response(
    started_at: float,
    *,
    content: str,
    model: str,
    provider: str,
    usage: ProviderUsage | None = None,
    raw: Mapping[str, Any] | None = None,
    error: ProviderError | None = None,
) -> ProviderResponse:
    latency_ms = int((time.perf_counter() - started_at) * 1000)
    return ProviderResponse(
        content=content,
        model=model,
        provider=provider,
        usage=usage or ProviderUsage(),
        latency_ms=latency_ms,
        raw=raw or {},
        error=error,
    )


def budget_from_provider_responses(
    responses: Iterable[ProviderResponse],
    *,
    rows: int,
) -> BudgetMetadata:
    response_list = list(responses)
    row_count = rows if rows > 0 else 1
    return BudgetMetadata(
        llm_calls_per_row=len(response_list) // row_count,
        input_tokens=sum(response.usage.input_tokens for response in response_list),
        output_tokens=sum(response.usage.output_tokens for response in response_list),
        total_tokens=sum(response.usage.total_tokens for response in response_list),
        latency_ms=sum(response.latency_ms for response in response_list),
        estimated_cost_usd=sum(response.usage.cost_usd for response in response_list),
    )
