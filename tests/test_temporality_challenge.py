#!/usr/bin/env python3
"""Tests for temporality challenge-set builders."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from core.temporality_challenge import summarize_temporality_rows, temporality_matches


def test_temporality_matches_planned_previous_and_seizure_free_history() -> None:
    text = (
        "I suggest that she starts levetiracetam next week. "
        "She was previously on carbamazepine. "
        "She had focal seizures in the past but is now seizure-free."
    )

    rows = temporality_matches("EA9999", text)
    categories = {row["category"] for row in rows}

    assert "planned_medication" in categories
    assert "previous_medication" in categories
    assert "seizure_free_historical_type" in categories
    assert all(row["snippet"] for row in rows)


def test_temporality_summary_counts_documents_by_category() -> None:
    rows = [
        {"document_id": "EA0001", "category": "planned_medication"},
        {"document_id": "EA0001", "category": "previous_medication"},
        {"document_id": "EA0002", "category": "previous_medication"},
    ]

    summary = summarize_temporality_rows(rows)

    assert summary["documents_with_matches"] == 2
    assert summary["match_count"] == 3
    assert summary["categories"]["previous_medication"]["documents"] == 2
