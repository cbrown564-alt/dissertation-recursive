from __future__ import annotations

import re
from dataclasses import dataclass


MONTHS_PER_YEAR = 12.0
WEEKS_PER_MONTH = 52.1775 / 12.0
DAYS_PER_MONTH = 365.25 / 12.0
MULTIPLE_VALUE = 3.0
UNKNOWN_RATE = 1000.0

UNIT_TO_MONTH_FACTOR = {
    "day": DAYS_PER_MONTH,
    "days": DAYS_PER_MONTH,
    "week": WEEKS_PER_MONTH,
    "weeks": WEEKS_PER_MONTH,
    "month": 1.0,
    "months": 1.0,
    "year": 1.0 / MONTHS_PER_YEAR,
    "years": 1.0 / MONTHS_PER_YEAR,
}


@dataclass(frozen=True)
class ParsedLabel:
    original: str
    monthly_rate: float | None
    pragmatic_class: str
    purist_class: str
    kind: str


def normalise_label_text(label: str) -> str:
    return " ".join(label.strip().lower().replace("–", "-").split())


def _value(token: str) -> float:
    token = token.strip().lower()
    if token == "multiple":
        return MULTIPLE_VALUE
    return float(token)


def _value_or_range(text: str) -> float:
    parts = [part.strip() for part in re.split(r"\s+to\s+|-", text) if part.strip()]
    values = [_value(part) for part in parts]
    return sum(values) / len(values)


def _period_to_months(value_text: str, unit: str) -> float:
    value = _value_or_range(value_text)
    unit_factor = UNIT_TO_MONTH_FACTOR[unit.lower()]
    if unit.lower().startswith("day"):
        return value / DAYS_PER_MONTH
    if unit.lower().startswith("week"):
        return value / WEEKS_PER_MONTH
    if unit.lower().startswith("year"):
        return value * MONTHS_PER_YEAR
    return value / unit_factor


def parse_monthly_rate(label: str) -> float | None:
    label = normalise_label_text(label)
    if label in {"no seizure frequency reference", "unknown"}:
        return UNKNOWN_RATE
    if label.startswith("unknown"):
        return UNKNOWN_RATE
    if label.startswith("seizure free"):
        return 0.0

    cluster = re.fullmatch(
        r"(?P<clusters>multiple|\d+(?:\.\d+)?(?:\s+(?:to|-)\s+\d+(?:\.\d+)?)?) "
        r"cluster per (?:(?P<period>multiple|\d+(?:\.\d+)?(?:\s+(?:to|-)\s+\d+(?:\.\d+)?)?) )?"
        r"(?P<unit>day|days|week|weeks|month|months|year|years), "
        r"(?P<count>multiple|\d+(?:\.\d+)?(?:\s+(?:to|-)\s+\d+(?:\.\d+)?)?) per cluster",
        label,
    )
    if cluster:
        clusters = _value_or_range(cluster.group("clusters"))
        period_months = _period_to_months(cluster.group("period") or "1", cluster.group("unit"))
        per_cluster = _value_or_range(cluster.group("count"))
        if period_months == 0:
            return None
        return clusters * per_cluster / period_months

    rate = re.fullmatch(
        r"(?P<count>multiple|\d+(?:\.\d+)?(?:\s+(?:to|-)\s+\d+(?:\.\d+)?)?) "
        r"per (?:(?P<period>multiple|\d+(?:\.\d+)?(?:\s+(?:to|-)\s+\d+(?:\.\d+)?)?) )?"
        r"(?P<unit>day|days|week|weeks|month|months|year|years)",
        label,
    )
    if rate:
        count = _value_or_range(rate.group("count"))
        period_months = _period_to_months(rate.group("period") or "1", rate.group("unit"))
        if period_months == 0:
            return None
        return count / period_months

    return None


def purist_class(monthly_rate: float | None) -> str:
    if monthly_rate is None or monthly_rate == UNKNOWN_RATE:
        return "UNK"
    if monthly_rate == 0:
        return "NS"
    if 0 < monthly_rate <= 0.16:
        return "<1/6M"
    if 0.16 < monthly_rate <= 0.18:
        return "1/6M"
    if 0.18 < monthly_rate <= 0.99:
        return "(1/6M,1/M)"
    if 0.99 < monthly_rate <= 1.1:
        return "1/M"
    if 1.1 < monthly_rate <= 3.9:
        return "(1/M,1/W)"
    if 3.9 < monthly_rate <= 4.1:
        return "1/W"
    if 4.1 < monthly_rate <= 29:
        return "(1/W,1/D)"
    return ">=1/D"


def pragmatic_class(monthly_rate: float | None) -> str:
    if monthly_rate is None or monthly_rate == UNKNOWN_RATE:
        return "UNK"
    if monthly_rate == 0:
        return "NS"
    if 0 < monthly_rate <= 1.1:
        return "infrequent"
    return "frequent"


def parse_label(label: str) -> ParsedLabel:
    monthly_rate = parse_monthly_rate(label)
    label_norm = normalise_label_text(label)
    if label_norm.startswith("seizure free"):
        kind = "seizure_free"
    elif label_norm.startswith("unknown") or label_norm == "no seizure frequency reference":
        kind = "unknown"
    elif "cluster" in label_norm:
        kind = "cluster"
    else:
        kind = "rate"
    return ParsedLabel(
        original=label,
        monthly_rate=monthly_rate,
        pragmatic_class=pragmatic_class(monthly_rate),
        purist_class=purist_class(monthly_rate),
        kind=kind,
    )
