from __future__ import annotations

import time
from collections import deque
from collections.abc import Iterable
from dataclasses import dataclass, field

from .base import ProviderRequest, ProviderResponse, ProviderUsage, timed_response


@dataclass
class MockProvider:
    responses: Iterable[str | ProviderResponse]
    provider_name: str = "mock"
    default_model: str = "mock-model"
    requests: list[ProviderRequest] = field(default_factory=list)

    def __post_init__(self) -> None:
        self._responses = deque(self.responses)

    def complete(self, request: ProviderRequest) -> ProviderResponse:
        self.requests.append(request)
        if not self._responses:
            raise RuntimeError("MockProvider has no queued responses left")

        queued = self._responses.popleft()
        if isinstance(queued, ProviderResponse):
            return queued

        started_at = time.perf_counter()
        return timed_response(
            started_at,
            content=queued,
            model=request.model or self.default_model,
            provider=self.provider_name,
            usage=ProviderUsage(
                input_tokens=sum(len(message.content.split()) for message in request.messages),
                output_tokens=len(queued.split()),
            ),
            raw={"mock": True},
        )
