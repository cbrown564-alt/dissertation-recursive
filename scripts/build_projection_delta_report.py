#!/usr/bin/env python3
"""Build raw-payload versus projected-canonical diagnostics for a run directory."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from core.io import read_json, write_csv, write_json, write_text
from core.projection_diagnostics import projection_delta_row, summarize_projection_deltas
from direct_baselines import parse_json_response


def _parse_payload(raw_path: Path) -> dict[str, Any] | None:
    parsed = parse_json_response(raw_path.read_text(encoding="utf-8"))
    return parsed.data if isinstance(parsed.data, dict) else None


def _discover_projection_pairs(calls_dir: Path) -> list[tuple[Path, Path]]:
    pairs: list[tuple[Path, Path]] = []
    for projection_path in sorted(calls_dir.rglob("canonical_projection.json")):
        raw_path = projection_path.parent / "raw_response.txt"
        if raw_path.exists():
            pairs.append((raw_path, projection_path))
    return pairs


def build_report(calls_dir: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []
    for raw_path, projection_path in _discover_projection_pairs(calls_dir):
        try:
            payload = _parse_payload(raw_path)
            canonical = read_json(projection_path)
        except Exception as exc:
            skipped.append({"raw_path": str(raw_path), "projection_path": str(projection_path), "error": str(exc)})
            continue
        if payload is None:
            skipped.append({"raw_path": str(raw_path), "projection_path": str(projection_path), "error": "raw response did not parse to object"})
            continue
        metadata = canonical.get("metadata", {}) if isinstance(canonical, dict) else {}
        rows.append(
            projection_delta_row(
                str(canonical.get("document_id") or projection_path.parent.name),
                str(metadata.get("harness_id") or projection_path.parent.parent.name),
                str(metadata.get("model_label") or projection_path.parent.parent.parent.name),
                payload,
                canonical,
            )
        )
    summary = summarize_projection_deltas(rows)
    summary["skipped"] = skipped
    return rows, summary


def markdown_report(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Projection Delta Report",
            "",
            f"Documents compared: {summary.get('documents', 0)}",
            f"Dropped fields after projection: {summary.get('dropped_field_count', 0)}",
            f"Added fields after projection: {summary.get('added_field_count', 0)}",
            f"Fields force-labelled current by projection shape: {summary.get('force_current_field_count', 0)}",
            f"Raw quote-like fields: {summary.get('raw_quote_count', 0)}",
            f"Projected evidence spans: {summary.get('projected_evidence_count', 0)}",
            f"Seizure-label changed documents: {summary.get('seizure_label_changed_documents', 0)}",
            f"Diagnosis-label changed documents: {summary.get('diagnosis_label_changed_documents', 0)}",
            f"Investigation-label changed documents: {summary.get('investigation_label_changed_documents', 0)}",
            f"Skipped pairs: {len(summary.get('skipped') or [])}",
            "",
        ]
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--calls-dir", required=True, help="Run calls directory containing raw_response.txt and canonical_projection.json files.")
    parser.add_argument("--output-dir", default="runs/projection_delta_report")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    rows, summary = build_report(Path(args.calls_dir))
    write_csv(output_dir / "projection_delta_rows.csv", rows)
    write_json(output_dir / "projection_delta_summary.json", summary)
    write_text(output_dir / "projection_delta_report.md", markdown_report(summary))
    print(f"wrote projection delta report for {summary.get('documents', 0)} documents to {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
