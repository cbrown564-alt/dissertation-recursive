#!/usr/bin/env python3
"""Build an ExECT Explorer model-overlay bundle from canonical extractions."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import jsonschema

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from core.manifests import artifact_record

SCHEMA_PATH = ROOT / "schemas" / "exect_explorer_model_overlay.schema.json"
DEFAULT_CANONICAL_DIR = ROOT / "runs" / "evidence_resolver" / "scored_batch" / "resolved"
DEFAULT_EXPLORER_DATA_DIR = ROOT / "exect-explorer" / "public" / "data"
DEFAULT_COMPARISON_REPORT = ROOT / "runs" / "evidence_resolver" / "scored_batch" / "comparison_report.json"
DEFAULT_RUN_MANIFEST = ROOT / "runs" / "evidence_resolver" / "scored_batch" / "run_manifest.json"
DEFAULT_OUTPUT = DEFAULT_EXPLORER_DATA_DIR / "model_overlays" / "h6fs_ev_validation_sample.json"

FIELD_GROUP_TO_GOLD_TYPES = {
    "current_anti_seizure_medications": {"Prescription"},
    "previous_anti_seizure_medications": {"Prescription"},
    "current_seizure_frequency": {"SeizureFrequency"},
    "seizure_types": {"Diagnosis", "PatientHistory", "SeizureFrequency"},
    "epilepsy_diagnosis": {"Diagnosis"},
    "eeg": {"Investigations"},
    "mri": {"Investigations"},
}


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _find_quote(text: str, quote: str) -> tuple[int | None, int | None]:
    if not quote:
        return None, None
    idx = text.find(quote)
    if idx < 0:
        idx = text.lower().find(quote.lower())
    if idx < 0:
        return None, None
    return idx, idx + len(quote)


def _overlaps(a_start: int | None, a_end: int | None, b_start: int, b_end: int) -> bool:
    if a_start is None or a_end is None:
        return False
    return max(a_start, b_start) < min(a_end, b_end)


def _gold_candidates(
    entities: list[dict[str, Any]],
    allowed_types: set[str],
    evidence_spans: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for entity in entities:
        if entity.get("type") not in allowed_types:
            continue
        start = int(entity["start"])
        end = int(entity["end"])
        if not any(_overlaps(span["char_start"], span["char_end"], start, end) for span in evidence_spans):
            continue
        candidates.append(
            {
                "id": str(entity["id"]),
                "type": str(entity["type"]),
                "start": start,
                "end": end,
                "text": str(entity.get("text", "")),
                "attributes": entity.get("attributes", {}),
            }
        )
    return candidates


def _alignment(value: Any, missingness: str | None, evidence: list[dict[str, Any]], gold: list[dict[str, Any]]) -> dict[str, str]:
    if missingness != "present" or value is None:
        return {"status": "not_present", "note": "Model did not mark this field present."}
    if gold:
        return {"status": "overlaps_gold", "note": "At least one evidence span overlaps a gold entity."}
    if evidence:
        return {"status": "evidence_only", "note": "Model has source evidence but no overlapping gold entity."}
    return {"status": "ungrounded", "note": "Model marked the field present without valid source evidence."}


def _evidence_spans(field: dict[str, Any], letter_text: str) -> list[dict[str, Any]]:
    spans: list[dict[str, Any]] = []
    raw_evidence = field.get("evidence") or []
    if not isinstance(raw_evidence, list):
        return spans
    for evidence in raw_evidence:
        if not isinstance(evidence, dict):
            continue
        quote = evidence.get("quote")
        if not isinstance(quote, str) or not quote:
            continue
        start, end = _find_quote(letter_text, quote)
        spans.append(
            {
                "quote": quote,
                "char_start": start,
                "char_end": end,
                "valid_quote": start is not None and end is not None,
            }
        )
    return spans


def _append_field(
    out: list[dict[str, Any]],
    *,
    field_id: str,
    field_path: str,
    field_group: str,
    value: Any,
    field: dict[str, Any],
    letter_text: str,
    gold_entities: list[dict[str, Any]],
    status: str | None = None,
) -> None:
    evidence = _evidence_spans(field, letter_text)
    gold = _gold_candidates(gold_entities, FIELD_GROUP_TO_GOLD_TYPES.get(field_group, set()), evidence)
    missingness = field.get("missingness")
    out.append(
        {
            "id": field_id,
            "field_path": field_path,
            "field_group": field_group,
            "value": str(value) if value is not None else None,
            "missingness": str(missingness) if missingness is not None else None,
            "temporality": str(field.get("temporality")) if field.get("temporality") is not None else None,
            "status": status,
            "evidence": evidence,
            "gold_candidates": gold,
            "alignment": _alignment(value, missingness, evidence, gold),
        }
    )


def canonical_to_model_fields(canonical: dict[str, Any], letter: dict[str, Any]) -> list[dict[str, Any]]:
    fields = canonical.get("fields", {})
    letter_text = letter.get("text", "")
    gold_entities = letter.get("entities", [])
    out: list[dict[str, Any]] = []

    for group in ("current_anti_seizure_medications", "previous_anti_seizure_medications"):
        for idx, med in enumerate(fields.get(group, [])):
            if not isinstance(med, dict):
                continue
            _append_field(
                out,
                field_id=f"{group}.{idx}.name",
                field_path=f"fields.{group}[{idx}].name",
                field_group=group,
                value=med.get("name"),
                field=med,
                letter_text=letter_text,
                gold_entities=gold_entities,
                status=med.get("status"),
            )

    for idx, seizure_type in enumerate(fields.get("seizure_types", [])):
        if not isinstance(seizure_type, dict):
            continue
        _append_field(
            out,
            field_id=f"seizure_types.{idx}.value",
            field_path=f"fields.seizure_types[{idx}].value",
            field_group="seizure_types",
            value=seizure_type.get("value"),
            field=seizure_type,
            letter_text=letter_text,
            gold_entities=gold_entities,
        )

    for group in ("current_seizure_frequency", "epilepsy_diagnosis"):
        field = fields.get(group)
        if isinstance(field, dict):
            _append_field(
                out,
                field_id=f"{group}.value",
                field_path=f"fields.{group}.value",
                field_group=group,
                value=field.get("value"),
                field=field,
                letter_text=letter_text,
                gold_entities=gold_entities,
            )

    for group in ("eeg", "mri"):
        field = fields.get(group)
        if isinstance(field, dict):
            value = field.get("result")
            if value in (None, "not_stated"):
                value = field.get("status")
            _append_field(
                out,
                field_id=f"{group}.result",
                field_path=f"fields.{group}.result",
                field_group=group,
                value=value,
                field=field,
                letter_text=letter_text,
                gold_entities=gold_entities,
                status=field.get("status"),
            )

    return out


def build_overlay_bundle(
    *,
    canonical_dir: Path,
    explorer_data_dir: Path,
    comparison_report: Path,
    run_manifest: Path | None,
    limit: int | None,
) -> dict[str, Any]:
    canonical_paths = sorted(canonical_dir.glob("*.json"))
    if limit is not None:
        canonical_paths = canonical_paths[:limit]
    if not canonical_paths:
        raise FileNotFoundError(f"no canonical JSON files found in {canonical_dir}")

    documents = []
    first_canonical: dict[str, Any] | None = None
    for canonical_path in canonical_paths:
        canonical = _read_json(canonical_path)
        first_canonical = first_canonical or canonical
        doc_id = canonical.get("document_id") or canonical_path.stem
        letter_path = explorer_data_dir / f"{doc_id}.json"
        if not letter_path.exists():
            raise FileNotFoundError(f"missing Explorer gold letter manifest: {letter_path}")
        letter = _read_json(letter_path)
        model_fields = canonical_to_model_fields(canonical, letter)
        documents.append(
            {
                "document_id": str(doc_id),
                "letter_path": str(letter_path),
                "canonical_path": str(canonical_path),
                "gold_entity_count": len(letter.get("entities", [])),
                "model_field_count": len(model_fields),
                "model_fields": model_fields,
            }
        )

    metadata = (first_canonical or {}).get("metadata", {})
    source = {
        "canonical_dir": str(canonical_dir),
        "explorer_data_dir": str(explorer_data_dir),
        "comparison_report": artifact_record(comparison_report),
    }
    if run_manifest and run_manifest.exists():
        source["run_manifest"] = artifact_record(run_manifest)

    bundle = {
        "schema_version": "2026-05-12",
        "artifact_class": "model_overlay",
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "source": source,
        "model": {
            "model_id": metadata.get("model"),
            "model_label": metadata.get("model_label"),
            "harness_id": metadata.get("harness_id"),
            "pipeline_id": (first_canonical or {}).get("pipeline_id"),
        },
        "documents": documents,
    }
    validate_bundle(bundle)
    return bundle


def validate_bundle(bundle: dict[str, Any], schema_path: Path = SCHEMA_PATH) -> None:
    schema = _read_json(schema_path)
    jsonschema.Draft202012Validator(schema).validate(bundle)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--canonical-dir", type=Path, default=DEFAULT_CANONICAL_DIR)
    parser.add_argument("--explorer-data-dir", type=Path, default=DEFAULT_EXPLORER_DATA_DIR)
    parser.add_argument("--comparison-report", type=Path, default=DEFAULT_COMPARISON_REPORT)
    parser.add_argument("--run-manifest", type=Path, default=DEFAULT_RUN_MANIFEST)
    parser.add_argument("--limit", type=int, default=3)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    bundle = build_overlay_bundle(
        canonical_dir=args.canonical_dir,
        explorer_data_dir=args.explorer_data_dir,
        comparison_report=args.comparison_report,
        run_manifest=args.run_manifest,
        limit=args.limit,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(bundle, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {len(bundle['documents'])} model overlay document(s) to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
