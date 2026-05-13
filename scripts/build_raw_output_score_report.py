#!/usr/bin/env python3
"""Score parsed raw model payloads directly, before canonical projection."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from core.io import read_json, write_csv, write_json, write_text
from core.raw_output_scoring import flatten_raw_summary, score_raw_payload
from core.scoring import DEFAULT_MARKUP_ROOT, load_gold
from direct_baselines import parse_json_response
from intake import DEFAULT_EXECT_ROOT


def _parse_payload(raw_path: Path) -> tuple[dict[str, Any] | None, str | None]:
    parsed = parse_json_response(raw_path.read_text(encoding="utf-8"))
    if isinstance(parsed.data, dict):
        return parsed.data, parsed.error
    return None, parsed.error or "raw response did not parse to object"


def _metadata_for_raw_path(raw_path: Path) -> dict[str, str]:
    projection_path = raw_path.parent / "canonical_projection.json"
    if projection_path.exists():
        canonical = read_json(projection_path)
        metadata = canonical.get("metadata", {}) if isinstance(canonical, dict) else {}
        return {
            "document_id": str(canonical.get("document_id") or raw_path.parent.name),
            "harness_id": str(metadata.get("harness_id") or raw_path.parent.parent.name),
            "model_label": str(metadata.get("model_label") or raw_path.parent.parent.parent.name),
        }
    return {
        "document_id": raw_path.parent.name,
        "harness_id": raw_path.parent.parent.name if raw_path.parent.parent else "",
        "model_label": raw_path.parent.parent.parent.name if raw_path.parent.parent.parent else "",
    }


def _score_row(metadata: dict[str, str], score: dict[str, Any]) -> dict[str, Any]:
    fields = score.get("field_scores", {})
    raw_counts = score.get("raw_counts", {})
    row: dict[str, Any] = {
        "document_id": metadata["document_id"],
        "model_label": metadata["model_label"],
        "harness_id": metadata["harness_id"],
        "raw_schema_valid": False,
    }
    for key, value in sorted(raw_counts.items()):
        row[f"raw_{key}_count"] = value
    for metric in [
        "medication_name",
        "medication_dose",
        "medication_dose_unit",
        "medication_frequency",
        "medication_full",
        "seizure_type",
        "seizure_type_collapsed",
    ]:
        metric_score = fields.get(metric, {})
        row[f"{metric}_f1"] = metric_score.get("f1")
        row[f"{metric}_tp"] = metric_score.get("tp")
        row[f"{metric}_fp"] = metric_score.get("fp")
        row[f"{metric}_fn"] = metric_score.get("fn")
    for metric in [
        "current_seizure_frequency_per_letter",
        "eeg",
        "mri",
        "epilepsy_diagnosis",
        "epilepsy_diagnosis_collapsed",
    ]:
        row[f"{metric}_correct"] = fields.get(metric, {}).get("correct")
    return row


def build_report(
    calls_dir: Path,
    markup_root: Path = DEFAULT_MARKUP_ROOT,
    exect_root: Path = DEFAULT_EXECT_ROOT,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    gold = load_gold(markup_root, exect_root)
    document_scores: list[dict[str, Any]] = []
    rows: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []
    for raw_path in sorted(calls_dir.rglob("raw_response.txt")):
        metadata = _metadata_for_raw_path(raw_path)
        document_id = metadata["document_id"]
        payload, error = _parse_payload(raw_path)
        if payload is None:
            skipped.append({"raw_path": str(raw_path), "document_id": document_id, "error": error or "parse failed"})
            document_scores.append({"available": False})
            continue
        document_gold = gold.get(document_id)
        if document_gold is None:
            skipped.append({"raw_path": str(raw_path), "document_id": document_id, "error": "missing gold"})
            document_scores.append({"available": False})
            continue
        score = score_raw_payload(document_id, payload, document_gold)
        document_scores.append(score)
        rows.append(_score_row(metadata, score))
    summary = flatten_raw_summary(f"raw:{calls_dir.name}", document_scores)
    summary["skipped"] = skipped
    return rows, summary


def markdown_report(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Raw Output Score Report",
            "",
            "Direct parsed-payload metrics before canonical projection.",
            "",
            f"Raw outputs available: {summary.get('documents_available', 0)} / {summary.get('documents_expected', 0)}",
            f"Raw schema-valid rate: {summary.get('raw_schema_valid_rate', 0.0)}",
            f"Medication name F1: {summary.get('medication_name_f1')}",
            f"Medication full F1: {summary.get('medication_full_f1')}",
            f"Seizure type F1: {summary.get('seizure_type_f1')}",
            f"Seizure type collapsed F1: {summary.get('seizure_type_f1_collapsed')}",
            f"Frequency per-letter accuracy: {summary.get('current_seizure_frequency_per_letter_accuracy')}",
            f"EEG accuracy: {summary.get('eeg_accuracy')}",
            f"MRI accuracy: {summary.get('mri_accuracy')}",
            f"Diagnosis accuracy: {summary.get('epilepsy_diagnosis_accuracy')}",
            f"Diagnosis collapsed accuracy: {summary.get('epilepsy_diagnosis_accuracy_collapsed')}",
            f"Skipped raw responses: {len(summary.get('skipped') or [])}",
            "",
        ]
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--calls-dir", required=True, help="Run calls directory containing raw_response.txt files.")
    parser.add_argument("--output-dir", default="runs/raw_output_score_report")
    parser.add_argument("--markup-root", default=str(DEFAULT_MARKUP_ROOT))
    parser.add_argument("--exect-root", default=str(DEFAULT_EXECT_ROOT))
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    rows, summary = build_report(Path(args.calls_dir), Path(args.markup_root), Path(args.exect_root))
    write_csv(output_dir / "raw_output_score_rows.csv", rows)
    write_json(output_dir / "raw_output_score_summary.json", summary)
    write_text(output_dir / "raw_output_score_report.md", markdown_report(summary))
    print(f"wrote raw output score report for {summary.get('documents_available', 0)} raw outputs to {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
