from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


_FREQ_RULES: list[tuple[re.Pattern[str], str, float | None]] = [
    (re.compile(r"seizure.?free", re.IGNORECASE), "seizure_free", 0.0),
    (re.compile(r"(\d+(?:\.\d+)?)\s*(?:times?|x)\s+(?:per\s+)?day", re.IGNORECASE), "per_day", None),
    (re.compile(r"(\d+(?:\.\d+)?)\s*(?:times?|x)\s+(?:per\s+)?week", re.IGNORECASE), "per_week", None),
    (re.compile(r"(\d+(?:\.\d+)?)\s*(?:times?|x)\s+(?:per\s+)?month", re.IGNORECASE), "per_month", None),
    (re.compile(r"daily", re.IGNORECASE), "per_day", 30.0),
    (re.compile(r"weekly", re.IGNORECASE), "per_week", 4.33),
    (re.compile(r"monthly", re.IGNORECASE), "per_month", 1.0),
    (re.compile(r"(\d+(?:\.\d+)?)\s*(?:per\s+)?year", re.IGNORECASE), "per_year", None),
]

_MONTHLY_MULTIPLIERS: dict[str, float] = {
    "per_day": 30.0,
    "per_week": 4.33,
    "per_month": 1.0,
    "per_year": 1 / 12,
    "seizure_free": 0.0,
}


@dataclass(frozen=True)
class NormalizedFrequency:
    raw: str
    unit: str
    monthly_rate: float | None
    normalized: bool


def normalize_frequency(raw: str) -> NormalizedFrequency:
    """Attempt to normalize a raw frequency string to a monthly rate."""
    if not isinstance(raw, str):
        return NormalizedFrequency(raw=str(raw), unit="unknown", monthly_rate=None, normalized=False)
    for pattern, unit, fixed_rate in _FREQ_RULES:
        m = pattern.search(raw)
        if not m:
            continue
        if fixed_rate is not None:
            return NormalizedFrequency(raw=raw, unit=unit, monthly_rate=fixed_rate, normalized=True)
        # Try to extract count from the match group
        try:
            count = float(m.group(1))
        except (IndexError, ValueError):
            count = 1.0
        rate = count * _MONTHLY_MULTIPLIERS.get(unit, 1.0)
        return NormalizedFrequency(raw=raw, unit=unit, monthly_rate=rate, normalized=True)
    return NormalizedFrequency(raw=raw, unit="unknown", monthly_rate=None, normalized=False)


def enrich_seizure_frequency(freq_data: dict[str, Any]) -> dict[str, Any]:
    """Enrich a seizure_frequency dict with normalization metadata.

    Returns an artifact dict; does not modify the extraction payload.
    """
    if not freq_data or not isinstance(freq_data, dict):
        return {"raw": freq_data, "normalized": False}
    raw = freq_data.get("value") or freq_data.get("raw") or str(freq_data)
    norm = normalize_frequency(str(raw))
    return {
        "raw": norm.raw,
        "unit": norm.unit,
        "monthly_rate": norm.monthly_rate,
        "normalized": norm.normalized,
    }
