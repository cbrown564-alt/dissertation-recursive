#!/usr/bin/env python3
"""Tests for maintained prompt contracts and canonical projection helpers."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from core.manifests import sha256_text
from core.prompts import build_h6_prompt, build_h6fs_prompt, build_h6full_prompt, prompt_artifact_report
from core.projection import RELAXED_PROJECTION_VERSION, projected_canonical
from model_expansion import (
    build_h6_prompt as legacy_build_h6_prompt,
    build_h6fs_prompt as legacy_build_h6fs_prompt,
    build_h6full_prompt as legacy_build_h6full_prompt,
)
from validate_extraction import validate_extraction


def _document() -> dict[str, object]:
    text = (
        "She takes levetiracetam 500 mg twice daily. "
        "She has focal seizures twice a month. "
        "EEG showed left temporal spikes. MRI was normal."
    )
    return {
        "text": text,
        "sentences": [
            {"sentence_id": "s1", "char_start": 0, "char_end": len(text), "text": text},
        ],
    }


def test_h6_prompt_contracts_are_available_from_core_and_legacy_imports() -> None:
    document = _document()

    assert legacy_build_h6_prompt(document, "H6_benchmark_only_coarse_json") == build_h6_prompt(
        document,
        "H6_benchmark_only_coarse_json",
    )
    assert legacy_build_h6fs_prompt(document, "H6fs_benchmark_only_coarse_json") == build_h6fs_prompt(
        document,
        "H6fs_benchmark_only_coarse_json",
    )
    assert legacy_build_h6full_prompt(document, "H6full_benchmark_json") == build_h6full_prompt(
        document,
        "H6full_benchmark_json",
    )


def test_h6fs_prompt_freezes_few_shot_status_contract() -> None:
    prompt = build_h6fs_prompt(_document(), "H6fs_benchmark_only_coarse_json")

    assert '"medication_names":[],"seizure_types":[],"epilepsy_diagnosis_type":null' in prompt
    assert '"unknown seizure type"' in prompt
    assert '"seizure free"' in prompt
    assert "Allowed seizure_type labels:" in prompt


def test_sanitized_prompt_style_removes_internal_run_artefacts() -> None:
    harness_id = "H6fs_benchmark_only_coarse_json"
    prompt = build_h6fs_prompt(_document(), harness_id, prompt_style="clinician")
    report = prompt_artifact_report(prompt, harness_id)

    assert "## Harness" not in prompt
    assert harness_id not in prompt
    assert "benchmark" not in prompt.lower()
    assert "Extract the requested current epilepsy fields" in prompt
    assert report["artefacts"]["mentions_harness"] is False
    assert report["artefacts"]["mentions_benchmark"] is False


def test_evidence_resolver_fallback_prompt_contract_is_frozen() -> None:
    template = Path("prompts/recovery/evidence_resolver_fallback.md").read_text(encoding="utf-8")

    assert "Do NOT change, normalise, interpret, or drop any value." in template
    assert "Evidence quotes must be **exact contiguous text copied from the source letter**." in template
    assert '"quote": null' in template
    assert "{source_text}" in template
    assert "{values_json}" in template
    assert sha256_text(template)


def test_multi_agent_verifier_and_corrector_prompt_contracts_are_frozen() -> None:
    verifier = Path("prompts/multi_agent_v2/verifier.md").read_text(encoding="utf-8")
    corrector = Path("prompts/multi_agent_v2/corrector.md").read_text(encoding="utf-8")

    assert "Only flag problems" in verifier
    assert '"flags": []' in verifier
    assert "Current medications with generic names are correct" in verifier
    assert "Benchmark-normalized labels are CORRECT" in verifier

    assert "Only change flagged fields" in corrector
    assert "return the original extraction unchanged" in corrector
    assert "Return the **complete canonical JSON**" in corrector
    assert "Medication names" in corrector and "generic names" in corrector


def test_projection_preserves_h6full_medication_tuple_and_investigations() -> None:
    projected = projected_canonical(
        "EA0001",
        "H6full_benchmark_json",
        "local_model",
        {
            "medications": [{"name": "levetiracetam", "dose": "500", "unit": "mg", "frequency": "twice daily"}],
            "seizure_types": ["focal impaired awareness seizure"],
            "epilepsy_diagnosis_type": "focal epilepsy",
            "current_seizure_frequency": "2 per month",
            "investigations": {"eeg": "abnormal left temporal spikes", "mri": "normal"},
        },
        {"provider_model_id": "qwen3.6:35b", "latency_ms": "12", "input_tokens": "100", "output_tokens": "50"},
        _document(),
    )

    medication = projected["fields"]["current_anti_seizure_medications"][0]
    assert medication["name"] == "levetiracetam"
    assert medication["dose"] == "500"
    assert medication["dose_unit"] == "mg"
    assert medication["frequency"] == "twice daily"
    assert projected["fields"]["seizure_types"][0]["value"] == "focal seizure"
    assert projected["fields"]["eeg"]["result"] == "abnormal"
    assert projected["fields"]["mri"]["result"] == "normal"
    assert projected["metadata"]["projection"] == RELAXED_PROJECTION_VERSION
    validate_extraction(projected, Path("schemas/canonical_extraction.schema.json"), require_present_evidence=False)


def test_projection_can_require_present_evidence_for_evidence_harnesses() -> None:
    projected = projected_canonical(
        "EA0001",
        "D3_candidate_plus_verifier",
        "frontier_model",
        {
            "current_anti_seizure_medications": [{"name": "levetiracetam", "quote": "levetiracetam 500 mg twice daily"}],
            "seizure_types": [{"label": "focal seizure", "quote": "focal seizures"}],
            "epilepsy_diagnosis_type": {"label": "focal epilepsy", "quote": "not in source"},
        },
        {},
        _document(),
        require_present_evidence=True,
    )

    assert len(projected["fields"]["current_anti_seizure_medications"]) == 1
    assert projected["fields"]["seizure_types"][0]["value"] == "focal seizure"
    assert projected["fields"]["epilepsy_diagnosis"]["value"] is None
