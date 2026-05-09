"""Smoke tests for gan_frequency label parser and category mappings.

Covers the label forms listed in PARSER_CONTRACT and the edge cases
from the minimal-repo comparison (WP2 acceptance criteria).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gan_frequency import label_to_categories, label_to_monthly_frequency, UNKNOWN_X


def _cats(label: str) -> tuple[str, str]:
    c = label_to_categories(label)
    return c["pragmatic"], c["purist"]


def test_3_to_4_per_month() -> None:
    x = label_to_monthly_frequency("3 to 4 per month")
    assert 3.0 <= x <= 4.0, x
    assert _cats("3 to 4 per month") == ("frequent", "(1/M,1/W)")


def test_hyphen_range_per_month() -> None:
    # "3-4 per month" normalizes hyphens to spaces → "3 4 per month"
    x = label_to_monthly_frequency("3-4 per month")
    assert 3.0 <= x <= 4.0, x
    assert _cats("3-4 per month") == ("frequent", "(1/M,1/W)")


def test_cluster_per_month() -> None:
    x = label_to_monthly_frequency("2 cluster per month, 6 per cluster")
    assert abs(x - 12.0) < 0.1, x
    assert _cats("2 cluster per month, 6 per cluster")[0] == "frequent"


def test_seizure_free_12_month() -> None:
    assert label_to_monthly_frequency("seizure free for 12 month") == 0.0
    assert _cats("seizure free for 12 month") == ("NS", "NS")


def test_seizure_free_multiple_month() -> None:
    assert label_to_monthly_frequency("seizure free for multiple month") == 0.0
    assert _cats("seizure free for multiple month") == ("NS", "NS")


def test_unknown() -> None:
    assert label_to_monthly_frequency("unknown") == UNKNOWN_X
    assert _cats("unknown") == ("UNK", "UNK")


def test_no_seizure_frequency_reference() -> None:
    assert label_to_monthly_frequency("no seizure frequency reference") == UNKNOWN_X
    assert _cats("no seizure frequency reference") == ("UNK", "UNK")


def test_1_per_month_is_infrequent() -> None:
    assert _cats("1 per month") == ("infrequent", "1/M")


def test_2_per_month_is_frequent() -> None:
    assert _cats("2 per month") == ("frequent", "(1/M,1/W)")


def test_1_per_week_is_frequent() -> None:
    assert _cats("1 per week")[0] == "frequent"
