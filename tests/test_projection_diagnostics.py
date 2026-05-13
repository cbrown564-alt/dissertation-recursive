#!/usr/bin/env python3
"""Tests for raw-payload versus canonical-projection diagnostics."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from core.projection import projected_canonical
from core.projection_diagnostics import projection_delta_row, summarize_projection_deltas


def _document() -> dict[str, object]:
    text = "She has focal impaired awareness seizures. EEG showed temporal spikes."
    return {"text": text, "sentences": [{"sentence_id": "s1", "char_start": 0, "char_end": len(text), "text": text}]}


def test_projection_delta_flags_label_normalization_and_forced_current() -> None:
    payload = {
        "medication_names": ["Keppra"],
        "seizure_types": ["focal impaired awareness seizure"],
        "epilepsy_diagnosis_type": "focal epilepsy",
        "investigations": {"eeg": "left temporal spikes"},
    }
    canonical = projected_canonical("EA0001", "H6_benchmark_only_coarse_json", "local", payload, {}, _document())

    row = projection_delta_row("EA0001", "H6_benchmark_only_coarse_json", "local", payload, canonical)

    assert row["raw_seizure_type_count"] == 1
    assert row["projected_seizure_type_count"] == 1
    assert row["seizure_label_changed"] is True
    assert row["eeg_label_changed"] is True
    assert row["force_current_field_count"] == 2


def test_projection_delta_summary_counts_changed_documents() -> None:
    rows = [
        {"dropped_field_count": 1, "added_field_count": 0, "raw_quote_count": 2, "projected_evidence_count": 1, "force_current_field_count": 3, "seizure_label_changed": True},
        {"dropped_field_count": 0, "added_field_count": 1, "raw_quote_count": 0, "projected_evidence_count": 0, "force_current_field_count": 2, "diagnosis_label_changed": True},
    ]

    summary = summarize_projection_deltas(rows)

    assert summary["documents"] == 2
    assert summary["dropped_field_count"] == 1
    assert summary["added_field_count"] == 1
    assert summary["force_current_field_count"] == 5
    assert summary["seizure_label_changed_documents"] == 1
    assert summary["diagnosis_label_changed_documents"] == 1
