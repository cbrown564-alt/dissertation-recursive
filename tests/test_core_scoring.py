#!/usr/bin/env python3
"""Regression tests for the corrected ExECTv2 scorer."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from core.io import write_csv
from core.scoring import GoldDocument, GoldSpan, load_gold, score_document


def _field(value: str | None, **extra: object) -> dict[str, object]:
    return {
        "value": value,
        "missingness": "present" if value else "not_stated",
        "temporality": "current",
        "evidence": [],
        "evidence_event_ids": [],
        **extra,
    }


def _canonical(**fields: object) -> dict[str, object]:
    defaults: dict[str, object] = {
        "current_anti_seizure_medications": [],
        "previous_anti_seizure_medications": [],
        "current_seizure_frequency": _field(None),
        "seizure_types": [],
        "eeg": _field(None, result=None, status=None),
        "mri": _field(None, result=None, status=None),
        "epilepsy_diagnosis": _field(None),
    }
    defaults.update(fields)
    return {"document_id": "EA0001", "fields": defaults, "metadata": {}}


def _score(data: dict[str, object], gold: GoldDocument) -> dict[str, object]:
    return score_document(data, "The patient takes Keppra and has focal seizures.", gold, Path("missing-schema.json"))


def test_load_gold_uses_fallback_column_when_name_is_null_string(tmp_path: Path) -> None:
    markup_root = tmp_path / "markup"
    exect_root = tmp_path / "letters"
    exect_root.mkdir()
    (exect_root / "EA0001.txt").write_text("Current medication is Keppra 500 mg twice daily.", encoding="utf-8")

    write_csv(
        markup_root / "MarkupPrescriptions.csv",
        [
            {
                "filename": "EA0001.txt",
                "start": "22",
                "end": "28",
                "unused1": "",
                "name": "null",
                "fallback_name": "Keppra",
                "dose": "500",
                "dose_unit": "mg",
                "frequency": "bd",
                "surface": "Keppra 500 mg twice daily",
            }
        ],
    )
    for filename in ["MarkupSeizureFrequency.csv", "MarkupInvestigations.csv", "MarkupDiagnosis.csv"]:
        (markup_root / filename).write_text("", encoding="utf-8")

    gold = load_gold(markup_root, exect_root)

    assert gold["EA0001"].medications[0]["name"] == "levetiracetam"


def test_score_document_expands_asm_synonyms_for_medication_names() -> None:
    gold = GoldDocument(document_id="EA0001", medications=[{"name": "levetiracetam", "dose": "", "dose_unit": "", "frequency": ""}])
    data = _canonical(
        current_anti_seizure_medications=[
            {
                "name": "Keppra",
                "dose": None,
                "dose_unit": None,
                "frequency": None,
                "status": "current",
                "missingness": "present",
                "temporality": "current",
                "evidence": [],
            }
        ]
    )

    score = _score(data, gold)

    assert score["field_scores"]["medication_name"]["f1"] == 1.0


def test_score_document_scores_medication_components_independently() -> None:
    gold = GoldDocument(
        document_id="EA0001",
        medications=[{"name": "levetiracetam", "dose": "500", "dose_unit": "mg", "frequency": "twice daily"}],
    )
    data = _canonical(
        current_anti_seizure_medications=[
            {
                "name": "Keppra",
                "dose": "500",
                "dose_unit": "milligrams",
                "frequency": "bd",
                "status": "current",
                "missingness": "present",
                "temporality": "current",
                "evidence": [],
            }
        ]
    )

    score = _score(data, gold)

    assert score["field_scores"]["medication_dose"]["f1"] == 1.0
    assert score["field_scores"]["medication_dose_unit"]["f1"] == 1.0
    assert score["field_scores"]["medication_frequency"]["f1"] == 1.0
    assert score["field_scores"]["medication_full"]["f1"] == 1.0


def test_score_document_reports_collapsed_seizure_type_labels() -> None:
    gold = GoldDocument(document_id="EA0001", seizure_types=["focal seizure"])
    data = _canonical(seizure_types=[_field("complex partial seizure")])

    score = _score(data, gold)

    assert score["field_scores"]["seizure_type_collapsed"]["f1"] == 1.0
    assert score["field_label_sets"]["seizure_type_collapsed"]["predicted"] == ["focal seizure or epilepsy"]


def test_score_document_uses_loose_frequency_matching_for_ranges() -> None:
    gold = GoldDocument(
        document_id="EA0001",
        seizure_frequencies=[
            {
                "value": "2-3 per 1 month",
                "count": "2-3",
                "period_count": "1",
                "period_unit": "month",
                "seizure_type": "focal seizure",
                "temporal_scope": "current",
                "surface": "2-3 seizures per month",
            }
        ],
    )
    data = _canonical(current_seizure_frequency=_field("2 seizures per month", seizure_type="focal seizure"))

    score = _score(data, gold)

    assert score["field_scores"]["current_seizure_frequency_relaxed"]["correct"] is False
    assert score["field_scores"]["current_seizure_frequency_loose"]["correct"] is True
    assert score["field_scores"]["current_seizure_frequency_per_letter"]["correct"] is True


def test_score_document_separates_quote_validity_from_evidence_support() -> None:
    gold = GoldDocument(
        document_id="EA0001",
        medications=[{"name": "levetiracetam", "dose": "", "dose_unit": "", "frequency": ""}],
        spans_by_group={"medications": [GoldSpan(18, 24, "Prescription", "Keppra")]},
    )
    data = _canonical(
        current_anti_seizure_medications=[
            {
                "name": "Keppra",
                "dose": None,
                "dose_unit": None,
                "frequency": None,
                "status": "current",
                "missingness": "present",
                "temporality": "current",
                "evidence": [{"quote": "focal seizures", "sentence_id": None, "char_start": None, "char_end": None}],
                "evidence_event_ids": [],
            }
        ]
    )

    score = _score(data, gold)

    assert score["quote_validity"]["rate"] == 1.0
    assert score["evidence_support"]["support_rate"] == 0.0
    assert score["evidence_support"]["claims"][0]["status"] == "co_located"


def test_score_document_marks_overlapping_wrong_claim_as_contradicting_gold() -> None:
    gold = GoldDocument(
        document_id="EA0001",
        medications=[{"name": "carbamazepine", "dose": "", "dose_unit": "", "frequency": ""}],
        spans_by_group={"medications": [GoldSpan(18, 24, "Prescription", "Keppra")]},
    )
    data = _canonical(
        current_anti_seizure_medications=[
            {
                "name": "Keppra",
                "dose": None,
                "dose_unit": None,
                "frequency": None,
                "status": "current",
                "missingness": "present",
                "temporality": "current",
                "evidence": [{"quote": "Keppra", "sentence_id": None, "char_start": None, "char_end": None}],
                "evidence_event_ids": [],
            }
        ]
    )

    score = _score(data, gold)

    assert score["quote_validity"]["rate"] == 1.0
    assert score["evidence_support"]["claims"][0]["status"] == "contradicts_gold"
