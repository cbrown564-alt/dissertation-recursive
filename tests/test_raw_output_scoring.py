#!/usr/bin/env python3
"""Tests for direct raw-output scoring helpers."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from core.raw_output_scoring import flatten_raw_summary, score_raw_payload
from core.scoring import GoldDocument


def test_score_raw_payload_scores_direct_fields_without_projection() -> None:
    gold = GoldDocument(
        document_id="EA0001",
        medications=[{"name": "levetiracetam", "dose": "500", "dose_unit": "mg", "frequency": "twice daily"}],
        seizure_frequencies=[
            {
                "value": "2 per 1 month",
                "count": "2",
                "period_count": "1",
                "period_unit": "month",
                "seizure_type": "focal seizure",
                "surface": "two seizures per month",
            }
        ],
        seizure_types=["focal seizure"],
        investigations={"eeg": "abnormal", "mri": "normal"},
        diagnoses=["focal epilepsy"],
    )
    payload = {
        "medications": [{"name": "levetiracetam", "dose": "500", "dose_unit": "mg", "frequency": "twice daily"}],
        "seizure_types": ["focal seizure"],
        "current_seizure_frequency": "2 per 1 month",
        "investigations": {"eeg": "abnormal", "mri": "normal"},
        "epilepsy_diagnosis_type": "focal epilepsy",
    }

    score = score_raw_payload("EA0001", payload, gold)

    assert score["schema_valid"] is False
    assert score["field_scores"]["medication_name"]["f1"] == 1.0
    assert score["field_scores"]["medication_full"]["f1"] == 1.0
    assert score["field_scores"]["seizure_type"]["f1"] == 1.0
    assert score["field_scores"]["current_seizure_frequency_per_letter"]["correct"] is True
    assert score["field_scores"]["eeg"]["correct"] is True
    assert score["field_scores"]["epilepsy_diagnosis"]["correct"] is True


def test_flatten_raw_summary_aggregates_document_metrics() -> None:
    scores = [
        {
            "available": True,
            "field_scores": {
                "medication_name": {"tp": 1, "fp": 0, "fn": 0},
                "medication_dose": {"tp": 0, "fp": 0, "fn": 1},
                "medication_dose_unit": {"tp": 1, "fp": 0, "fn": 0},
                "medication_frequency": {"tp": 1, "fp": 0, "fn": 0},
                "medication_full": {"tp": 1, "fp": 0, "fn": 0},
                "seizure_type": {"tp": 1, "fp": 0, "fn": 0},
                "seizure_type_collapsed": {"tp": 1, "fp": 0, "fn": 0},
                "eeg": {"correct": True},
            },
            "raw_counts": {"medication": 1},
        }
    ]

    summary = flatten_raw_summary("raw:test", scores)

    assert summary["documents_available"] == 1
    assert summary["raw_schema_valid_rate"] == 0.0
    assert summary["medication_name_f1"] == 1.0
    assert summary["medication_dose_f1"] == 0.0
    assert summary["eeg_accuracy"] == 1.0
    assert summary["raw_medication_count"] == 1
