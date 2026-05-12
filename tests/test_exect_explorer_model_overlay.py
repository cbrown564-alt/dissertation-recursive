#!/usr/bin/env python3
"""Tests for ExECT Explorer model-overlay bundle generation."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema

sys.path.insert(0, str(Path(__file__).parent.parent / "exect-explorer" / "scripts"))

from build_model_overlay import build_overlay_bundle, canonical_to_model_fields


def test_build_model_overlay_bundle_matches_schema() -> None:
    bundle = build_overlay_bundle(
        canonical_dir=Path("runs/evidence_resolver/scored_batch/resolved"),
        explorer_data_dir=Path("exect-explorer/public/data"),
        comparison_report=Path("runs/evidence_resolver/scored_batch/comparison_report.json"),
        run_manifest=Path("runs/evidence_resolver/scored_batch/run_manifest.json"),
        limit=2,
    )
    schema = json.loads(Path("schemas/exect_explorer_model_overlay.schema.json").read_text(encoding="utf-8"))

    jsonschema.Draft202012Validator(schema).validate(bundle)
    assert bundle["artifact_class"] == "model_overlay"
    assert len(bundle["documents"]) == 2
    assert bundle["documents"][0]["model_field_count"] == len(bundle["documents"][0]["model_fields"])
    assert "exect_annotations_" not in json.dumps(bundle)


def test_model_overlay_resolves_evidence_spans_and_gold_candidates() -> None:
    canonical = json.loads(Path("runs/evidence_resolver/scored_batch/resolved/EA0008.json").read_text(encoding="utf-8"))
    letter = json.loads(Path("exect-explorer/public/data/EA0008.json").read_text(encoding="utf-8"))

    fields = canonical_to_model_fields(canonical, letter)
    diagnosis = next(field for field in fields if field["field_path"] == "fields.epilepsy_diagnosis.value")
    seizure_type = next(field for field in fields if field["field_path"] == "fields.seizure_types[0].value")

    assert diagnosis["evidence"][0]["valid_quote"] is True
    assert diagnosis["alignment"]["status"] == "overlaps_gold"
    assert diagnosis["gold_candidates"][0]["type"] == "Diagnosis"
    assert seizure_type["evidence"][0]["valid_quote"] is True
