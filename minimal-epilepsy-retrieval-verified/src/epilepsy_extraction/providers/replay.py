from __future__ import annotations

import json
import time
from collections import deque
from pathlib import Path
from typing import Any

from .base import ProviderError, ProviderRequest, ProviderResponse, ProviderUsage, timed_response


class ReplayProvider:
    provider_name = "replay"

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        responses = payload["responses"] if isinstance(payload, dict) else payload
        self._responses = deque(_response_from_dict(response) for response in responses)
        self.requests: list[ProviderRequest] = []

    def complete(self, request: ProviderRequest) -> ProviderResponse:
        self.requests.append(request)
        if not self._responses:
            started_at = time.perf_counter()
            return timed_response(
                started_at,
                content="",
                model=request.model,
                provider=self.provider_name,
                error=ProviderError(
                    type="replay_exhausted",
                    message=f"No replay responses left in {self.path}",
                    retryable=False,
                ),
            )
        response = self._responses.popleft()
        if response.model:
            return response
        return ProviderResponse(
            content=response.content,
            model=request.model,
            provider=response.provider,
            usage=response.usage,
            latency_ms=response.latency_ms,
            raw=response.raw,
            error=response.error,
        )


def _response_from_dict(data: dict[str, Any]) -> ProviderResponse:
    usage_data = data.get("usage", {})
    error_data = data.get("error")
    return ProviderResponse(
        content=data.get("content", ""),
        model=data.get("model", ""),
        provider=data.get("provider", "replay"),
        usage=ProviderUsage(
            input_tokens=int(usage_data.get("input_tokens", 0)),
            output_tokens=int(usage_data.get("output_tokens", 0)),
            cost_usd=float(usage_data.get("cost_usd", 0.0)),
        ),
        latency_ms=int(data.get("latency_ms", 0)),
        raw=data.get("raw", {}),
        error=ProviderError(**error_data) if error_data else None,
    )
