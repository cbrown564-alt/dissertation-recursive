from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any


EVENT_TYPES = frozenset(
    {
        "context_built",
        "provider_call_started",
        "provider_call_finished",
        "parse_attempted",
        "parse_repaired",
        "candidate_spans_selected",
        "field_extraction_completed",
        "verification_completed",
        "aggregation_completed",
        "budget_limit_hit",
        "warning_emitted",
        "escalation_decision",
    }
)


@dataclass(frozen=True)
class HarnessEvent:
    event_type: str
    row_id: str
    sequence_index: int
    component: str = ""
    event_id: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    duration_ms: int = 0
    summary: str = ""
    metrics: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    error: str = ""
    quote_bearing: bool = False

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["event_id"] = self.event_id or f"{self.row_id}:{self.sequence_index}:{self.event_type}"
        return data


def harness_event(
    event_type: str,
    row_id: str,
    sequence_index: int,
    *,
    component: str = "",
    summary: str = "",
    metrics: dict[str, Any] | None = None,
    warnings: list[str] | None = None,
    error: str = "",
    duration_ms: int = 0,
    quote_bearing: bool = False,
) -> HarnessEvent:
    if event_type not in EVENT_TYPES:
        raise ValueError(f"Unsupported harness event type: {event_type!r}")
    return HarnessEvent(
        event_type=event_type,
        row_id=str(row_id),
        sequence_index=sequence_index,
        component=component,
        summary=summary,
        metrics=metrics or {},
        warnings=[str(warning) for warning in (warnings or [])],
        error=error,
        duration_ms=duration_ms,
        quote_bearing=quote_bearing,
    )


def summarize_harness_events(events: list[HarnessEvent]) -> dict[str, Any]:
    counts = Counter(event.event_type for event in events)
    component_counts: dict[str, int] = defaultdict(int)
    warning_count = 0
    errors = 0
    total_duration = 0
    for event in events:
        if event.component:
            component_counts[event.component] += 1
        warning_count += len(event.warnings)
        errors += 1 if event.error else 0
        total_duration += event.duration_ms
    return {
        "event_count": len(events),
        "event_type_counts": dict(sorted(counts.items())),
        "component_counts": dict(sorted(component_counts.items())),
        "provider_calls": counts.get("provider_call_started", 0),
        "parse_attempts": counts.get("parse_attempted", 0),
        "parse_repair_attempts": counts.get("parse_repaired", 0),
        "verifier_passes": counts.get("verification_completed", 0),
        "escalation_decisions": counts.get("escalation_decision", 0),
        "warnings": warning_count,
        "errors": errors,
        "duration_ms": total_duration,
        "quote_bearing_events": sum(1 for event in events if event.quote_bearing),
    }


def event_dicts(events: list[HarnessEvent]) -> list[dict[str, Any]]:
    return [event.to_dict() for event in events]
