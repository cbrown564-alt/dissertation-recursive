#!/usr/bin/env python3
"""Unit tests for the Option-C hybrid evidence resolver."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from evidence_resolver import (
    ResolvableValue,
    ResolutionResult,
    ResolverStats,
    collect_resolvable_values,
    deterministic_resolve,
    _find_exact_quote,
    _find_normalized_quote,
    _find_synonym_quote,
    _find_medication_quote,
    _find_seizure_type_quote,
    _find_diagnosis_quote,
    _find_investigation_quote,
    _expand_to_sentence,
    _inject_evidence,
    build_fallback_prompt,
    parse_fallback_response,
    resolve_evidence_hybrid,
)
from normalization import (
    ASM_SYNONYMS,
    SEIZURE_TYPE_SYNONYMS,
    DIAGNOSIS_SYNONYMS,
    canonical_medication_name,
    canonical_seizure_type,
    canonical_diagnosis,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_LETTER = """Dr Smith
Epilepsy Clinic
15 March 2024

Dear Dr Smith,

Thank you for referring this 34-year-old gentleman with epilepsy.

Current antiepileptic medication: lamotrigine 75 mg twice a day,
levetiracetam 1,000 mg bd and Keppra 500 mg nocte.

He reports complex partial seizures approximately 2–3 per month.
His diagnosis is JME.

EEG was normal. MRI brain showed no abnormality.

Yours sincerely,
Dr Jones
"""

SAMPLE_CANONICAL = {
    "document_id": "EA9999",
    "pipeline_id": "test_h6fs",
    "fields": {
        "current_anti_seizure_medications": [
            {
                "name": "lamotrigine",
                "dose": "75",
                "dose_unit": "mg",
                "frequency": "twice a day",
                "status": "current",
                "missingness": "present",
                "temporality": "current",
                "evidence": [],
                "evidence_event_ids": [],
            },
            {
                "name": "levetiracetam",
                "dose": "1000",
                "dose_unit": "mg",
                "frequency": "twice daily",
                "status": "current",
                "missingness": "present",
                "temporality": "current",
                "evidence": [],
                "evidence_event_ids": [],
            },
        ],
        "previous_anti_seizure_medications": [],
        "current_seizure_frequency": {
            "value": "2 to 3 per month",
            "missingness": "present",
            "temporality": "current",
            "temporal_scope": "per month",
            "seizure_type": None,
            "evidence": [],
            "evidence_event_ids": [],
        },
        "seizure_types": [
            {
                "value": "focal impaired awareness seizure",
                "missingness": "present",
                "temporality": "current",
                "evidence": [],
                "evidence_event_ids": [],
            }
        ],
        "eeg": {
            "status": "completed",
            "result": "normal",
            "missingness": "present",
            "temporality": "current",
            "evidence": [],
            "evidence_event_ids": [],
        },
        "mri": {
            "status": "completed",
            "result": "normal",
            "missingness": "present",
            "temporality": "current",
            "evidence": None,
            "evidence_event_ids": [],
        },
        "epilepsy_diagnosis": {
            "value": "juvenile myoclonic epilepsy",
            "missingness": "present",
            "temporality": "current",
            "evidence": [],
            "evidence_event_ids": [],
        },
    },
    "events": [],
    "metadata": {},
}


# ---------------------------------------------------------------------------
# Collect values
# ---------------------------------------------------------------------------

def test_collect_resolvable_values_counts() -> None:
    values = collect_resolvable_values(SAMPLE_CANONICAL)
    paths = {v.path for v in values}
    assert "fields.current_anti_seizure_medications[0].name" in paths
    assert "fields.current_anti_seizure_medications[1].name" in paths
    assert "fields.current_seizure_frequency.value" in paths
    assert "fields.seizure_types[0].value" in paths
    assert "fields.epilepsy_diagnosis.value" in paths
    assert "fields.eeg.result" in paths
    assert "fields.mri.result" in paths
    # eeg.status is present but mri has evidence: null, which is fine
    # status should also be collected
    assert "fields.eeg.status" in paths


def test_collect_skips_not_present() -> None:
    canonical = json.loads(json.dumps(SAMPLE_CANONICAL))
    canonical["fields"]["seizure_types"][0]["missingness"] = "not_stated"
    values = collect_resolvable_values(canonical)
    assert all(v.path != "fields.seizure_types[0].value" for v in values)


# ---------------------------------------------------------------------------
# Deterministic matchers
# ---------------------------------------------------------------------------

def test_find_exact_quote() -> None:
    assert _find_exact_quote(SAMPLE_LETTER, "lamotrigine") == "lamotrigine"
    assert _find_exact_quote(SAMPLE_LETTER, "Lamotrigine") == "lamotrigine"
    assert _find_exact_quote(SAMPLE_LETTER, "nonexistent") is None


def test_find_normalized_quote_smart_quotes() -> None:
    text = 'She takes \u201cKeppra\u201d 500 mg daily.'
    assert _find_normalized_quote(text, "Keppra") == "Keppra"


def test_find_normalized_quote_dash() -> None:
    # 2–3 uses an en-dash in the sample letter
    assert _find_normalized_quote(SAMPLE_LETTER, "2-3") == "2\u20133"


def test_find_medication_quote_synonym_brand() -> None:
    # Letter contains only the brand name; resolver should map back via synonym table
    text = "He takes Keppra 500 mg daily."
    quote = _find_medication_quote(text, "levetiracetam")
    assert quote is not None
    assert "Keppra" in quote


def test_find_medication_quote_misspelling() -> None:
    text = "He takes levitiracetam 500 mg daily."
    quote = _find_medication_quote(text, "levetiracetam")
    assert quote is not None
    assert "levitiracetam" in quote.lower()


def test_find_seizure_type_quote_synonym() -> None:
    # "complex partial" in letter maps to "focal impaired awareness seizure"
    quote = _find_seizure_type_quote(SAMPLE_LETTER, "focal impaired awareness seizure")
    assert quote is not None
    assert "complex partial" in quote.lower()


def test_find_diagnosis_quote_synonym() -> None:
    # "JME" in letter maps to "juvenile myoclonic epilepsy"
    quote = _find_diagnosis_quote(SAMPLE_LETTER, "juvenile myoclonic epilepsy")
    assert quote is not None
    assert "JME" in quote


def test_find_investigation_quote_exact() -> None:
    quote = _find_investigation_quote(SAMPLE_LETTER, "normal")
    assert quote is not None
    assert "normal" in quote.lower()


def test_expand_to_sentence() -> None:
    quote = _expand_to_sentence(SAMPLE_LETTER, "lamotrigine")
    assert "Current antiepileptic medication" in quote


# ---------------------------------------------------------------------------
# Deterministic resolve (full wrapper)
# ---------------------------------------------------------------------------

def test_deterministic_resolve_medication_brand() -> None:
    text = "He takes Keppra 500 mg daily."
    value = ResolvableValue(
        path="fields.current_anti_seizure_medications[0].name",
        category="medication",
        value="levetiracetam",
    )
    result = deterministic_resolve(text, value, expand_sentence=True)
    assert result is not None
    assert result.grounded_by == "synonym"
    assert "Keppra" in (result.quote or "")


def test_deterministic_resolve_seizure_type() -> None:
    value = ResolvableValue(
        path="fields.seizure_types[0].value",
        category="seizure_type",
        value="focal impaired awareness seizure",
    )
    result = deterministic_resolve(SAMPLE_LETTER, value, expand_sentence=True)
    assert result is not None
    assert result.grounded_by == "synonym"
    assert "complex partial" in (result.quote or "").lower()


def test_deterministic_resolve_frequency() -> None:
    # Letter contains en-dash "2–3"; canonical value uses hyphen "2-3"
    value = ResolvableValue(
        path="fields.current_seizure_frequency.value",
        category="frequency",
        value="2-3 per month",
    )
    result = deterministic_resolve(SAMPLE_LETTER, value, expand_sentence=True)
    assert result is not None
    assert "2" in (result.quote or "")


def test_deterministic_resolve_ungrounded() -> None:
    value = ResolvableValue(
        path="fields.current_anti_seizure_medications[0].name",
        category="medication",
        value="phenytoin",  # Not in sample letter
    )
    result = deterministic_resolve(SAMPLE_LETTER, value, expand_sentence=True)
    assert result is None


# ---------------------------------------------------------------------------
# Fallback prompt & parsing
# ---------------------------------------------------------------------------

def test_build_fallback_prompt_contains_values() -> None:
    unresolved = [
        ResolvableValue(path="fields.x.value", category="medication", value="phenytoin"),
    ]
    prompt = build_fallback_prompt("Source text here", unresolved)
    assert "phenytoin" in prompt
    assert "Source text here" in prompt
    assert "fields.x.value" in prompt


def test_parse_fallback_response_json() -> None:
    text = json.dumps(
        {
            "groundings": [
                {"path": "fields.x.value", "quote": "She takes phenytoin 100 mg."}
            ]
        }
    )
    mapping = parse_fallback_response(text)
    assert mapping == {"fields.x.value": "She takes phenytoin 100 mg."}


def test_parse_fallback_response_markdown_fenced() -> None:
    text = (
        "```json\n"
        + json.dumps(
            {"groundings": [{"path": "fields.y.value", "quote": "quote here"}]}
        )
        + "\n```"
    )
    mapping = parse_fallback_response(text)
    assert mapping == {"fields.y.value": "quote here"}


def test_parse_fallback_response_alternative_keys() -> None:
    text = json.dumps(
        {
            "decisions": [
                {
                    "path": "fields.z.value",
                    "evidence": {"quote": "evidence quote"},
                }
            ]
        }
    )
    mapping = parse_fallback_response(text)
    assert mapping == {"fields.z.value": "evidence quote"}


# ---------------------------------------------------------------------------
# Evidence injection
# ---------------------------------------------------------------------------

def test_inject_evidence_medication() -> None:
    canonical = json.loads(json.dumps(SAMPLE_CANONICAL))
    _inject_evidence(canonical, "fields.current_anti_seizure_medications[0].name", "test quote")
    meds = canonical["fields"]["current_anti_seizure_medications"]
    assert meds[0]["evidence"] == [
        {"quote": "test quote", "sentence_id": None, "char_start": None, "char_end": None}
    ]


def test_inject_evidence_scalar() -> None:
    canonical = json.loads(json.dumps(SAMPLE_CANONICAL))
    _inject_evidence(canonical, "fields.epilepsy_diagnosis.value", "dx quote")
    assert canonical["fields"]["epilepsy_diagnosis"]["evidence"] == [
        {"quote": "dx quote", "sentence_id": None, "char_start": None, "char_end": None}
    ]


def test_inject_evidence_dedupes() -> None:
    canonical = json.loads(json.dumps(SAMPLE_CANONICAL))
    _inject_evidence(canonical, "fields.epilepsy_diagnosis.value", "dx quote")
    _inject_evidence(canonical, "fields.epilepsy_diagnosis.value", "dx quote")
    assert len(canonical["fields"]["epilepsy_diagnosis"]["evidence"]) == 1


# ---------------------------------------------------------------------------
# End-to-end hybrid (deterministic-only, no model)
# ---------------------------------------------------------------------------

def test_resolve_evidence_hybrid_deterministic_only() -> None:
    resolved, stats = resolve_evidence_hybrid(
        SAMPLE_CANONICAL, SAMPLE_LETTER, model_call=None
    )
    # Most values in SAMPLE_CANONICAL should match deterministically
    assert stats.deterministic_hits >= 4
    assert stats.fallback_hits == 0
    assert stats.ungrounded <= stats.total_values - stats.deterministic_hits

    # Verify quote validity
    from validate_extraction import check_quote_validity
    total, failures = check_quote_validity(resolved, SAMPLE_LETTER)
    assert len(failures) == 0, f"Invalid quotes at: {failures}"

    # Verify evidence was injected into the right places
    meds = resolved["fields"]["current_anti_seizure_medications"]
    assert len(meds[0]["evidence"]) > 0
    assert len(meds[1]["evidence"]) > 0


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

def test_resolver_stats_math() -> None:
    stats = ResolverStats(total_values=10, deterministic_hits=7, fallback_hits=2, ungrounded=1)
    assert stats.fallback_rate == 0.2
    assert stats.ungrounded_rate == 0.1
    d = stats.to_dict()
    assert d["fallback_rate"] == 0.2
    assert d["ungrounded_rate"] == 0.1


if __name__ == "__main__":
    raise SystemExit(0)
