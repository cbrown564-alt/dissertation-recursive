import json

from epilepsy_extraction.providers import (
    MockProvider,
    ProviderMessage,
    ProviderRequest,
    ProviderResponse,
    ProviderUsage,
    ReplayProvider,
    budget_from_provider_responses,
)


def _request() -> ProviderRequest:
    return ProviderRequest(
        messages=[ProviderMessage(role="user", content="Return JSON please")],
        model="test-model",
    )


def test_mock_provider_returns_queued_content_and_tracks_usage() -> None:
    provider = MockProvider(['{"ok": true}'])

    response = provider.complete(_request())

    assert response.ok
    assert response.content == '{"ok": true}'
    assert response.provider == "mock"
    assert response.usage.input_tokens == 3
    assert response.usage.output_tokens == 2
    assert provider.requests[0].model == "test-model"


def test_replay_provider_reads_json_responses(tmp_path) -> None:
    replay_path = tmp_path / "replay.json"
    replay_path.write_text(
        json.dumps(
            {
                "responses": [
                    {
                        "content": '{"label": "2 per month"}',
                        "provider": "captured",
                        "usage": {"input_tokens": 10, "output_tokens": 5},
                        "latency_ms": 123,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    provider = ReplayProvider(replay_path)

    response = provider.complete(_request())

    assert response.content == '{"label": "2 per month"}'
    assert response.model == "test-model"
    assert response.provider == "captured"
    assert response.usage.total_tokens == 15
    assert response.latency_ms == 123


def test_replay_provider_exhaustion_returns_error(tmp_path) -> None:
    replay_path = tmp_path / "empty.json"
    replay_path.write_text("[]", encoding="utf-8")
    provider = ReplayProvider(replay_path)

    response = provider.complete(_request())

    assert not response.ok
    assert response.error is not None
    assert response.error.type == "replay_exhausted"


def test_budget_from_provider_responses_accumulates_usage() -> None:
    budget = budget_from_provider_responses(
        [
            ProviderResponse(
                content="a",
                model="m",
                provider="p",
                usage=ProviderUsage(input_tokens=10, output_tokens=5, cost_usd=0.02),
                latency_ms=100,
            ),
            ProviderResponse(
                content="b",
                model="m",
                provider="p",
                usage=ProviderUsage(input_tokens=7, output_tokens=3, cost_usd=0.03),
                latency_ms=80,
            ),
        ],
        rows=2,
    )

    assert budget.llm_calls_per_row == 1
    assert budget.input_tokens == 17
    assert budget.output_tokens == 8
    assert budget.total_tokens == 25
    assert budget.latency_ms == 180
    assert budget.estimated_cost_usd == 0.05
