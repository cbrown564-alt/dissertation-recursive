#!/usr/bin/env python3
"""Provider-neutral model adapter helpers."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from model_providers import ModelRequest, TokenUsage, detect_token_budget_alarm
from model_registry import ModelSpec


def _model(max_output_tokens: int = 512) -> ModelSpec:
    return ModelSpec(
        label="test_reasoning_model",
        provider="openai",
        provider_model_id="gpt-test",
        api_surface="responses",
        sdk_package=None,
        sdk_version=None,
        context_window_tokens=128000,
        max_output_tokens=max_output_tokens,
        structured_output=None,
        temperature=0.0,
        seed_supported=False,
        pricing={
            "input_per_million": None,
            "output_per_million": None,
            "cache_read_per_million": None,
            "cache_write_per_million": None,
        },
        pricing_snapshot_date=None,
        region=None,
        billing_currency="USD",
        deprecation_or_alias_behavior=None,
        raw={},
    )


def test_detect_token_budget_alarm_for_reasoning_exhaustion() -> None:
    request = ModelRequest(prompt="prompt", model=_model(), harness_id="h")
    alarm = detect_token_budget_alarm(
        request=request,
        text="",
        usage=TokenUsage(input_tokens=100, output_tokens=512),
        stop_reason="incomplete",
        provider_metadata={
            "status": "incomplete",
            "incomplete_details": {"reason": "max_output_tokens"},
            "output_tokens_details": {"reasoning_tokens": 512},
        },
    )

    assert alarm["triggered"] is True
    assert "incomplete_reason=max_output_tokens" in alarm["reasons"]
    assert "empty_text_with_reasoning_tokens_near_budget" in alarm["reasons"]


def test_detect_token_budget_alarm_stays_quiet_for_normal_response() -> None:
    request = ModelRequest(prompt="prompt", model=_model(), harness_id="h")
    alarm = detect_token_budget_alarm(
        request=request,
        text='{"ok": true}',
        usage=TokenUsage(input_tokens=100, output_tokens=120),
        stop_reason="completed",
        provider_metadata={},
    )

    assert alarm["triggered"] is False
