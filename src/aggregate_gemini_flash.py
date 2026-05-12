#!/usr/bin/env python3
"""Aggregate Gemini Flash validation results from multiple run directories."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from evaluate import DEFAULT_MARKUP_ROOT, flatten_summary, load_gold, score_document
from intake import DEFAULT_EXECT_ROOT, preprocess_document
from validate_extraction import DEFAULT_SCHEMA


def load_h0_canonical(run_dir: Path) -> dict[str, dict]:
    """Load canonical.json files from an H0 stage-a-smoke run."""
    results = {}
    base = run_dir / "gemini_3_1_flash" / "H0_strict_canonical"
    for path in base.glob("*/canonical.json"):
        doc_id = path.parent.name
        try:
            results[doc_id] = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return results


def load_h6h7_projections(run_dir: Path) -> dict[str, dict[str, dict]]:
    """Load canonical_projection.json files from an h6-h7 diagnostic run.
    Returns {harness_id: {doc_id: data}}."""
    results: dict[str, dict[str, dict]] = {}
    proj_dir = run_dir / "projections" / "gemini_3_1_flash"
    if not proj_dir.exists():
        return results
    for harness_dir in proj_dir.iterdir():
        if not harness_dir.is_dir():
            continue
        harness_id = harness_dir.name
        for doc_dir in harness_dir.iterdir():
            path = doc_dir / "canonical_projection.json"
            if path.exists():
                try:
                    results.setdefault(harness_id, {})[doc_dir.name] = json.loads(path.read_text(encoding="utf-8"))
                except Exception:
                    pass
    return results


def score_all(
    label: str,
    outputs: dict[str, dict],
    gold: dict,
    schema_path: Path,
    exect_root: Path,
) -> dict[str, float]:
    scores = []
    for doc_id, data in sorted(outputs.items()):
        document = preprocess_document(doc_id, exect_root)
        gold_doc = gold.get(doc_id)
        if gold_doc is None:
            continue
        scores.append(score_document(data, document["text"], gold_doc, schema_path))
    if not scores:
        return {}
    return flatten_summary(label, scores)


def main() -> int:
    exect_root = Path(DEFAULT_EXECT_ROOT)
    markup_root = Path(DEFAULT_MARKUP_ROOT)
    schema_path = Path(DEFAULT_SCHEMA)
    gold = load_gold(markup_root, exect_root)

    # H0
    h0_dir = Path("runs/model_expansion/gemini_flash_h0_val_final")
    h0_outputs = load_h0_canonical(h0_dir)
    if len(h0_outputs) < 40:
        # Fallback to partial run
        h0_dir_partial = Path("runs/model_expansion/gemini_flash_h0_val_full")
        h0_outputs_partial = load_h0_canonical(h0_dir_partial)
        # Merge, preferring final
        for doc_id, data in h0_outputs_partial.items():
            if doc_id not in h0_outputs:
                h0_outputs[doc_id] = data

    # H6/H7
    h6h7_dir = Path("runs/model_expansion/gemini_flash_h6h7_val_full")
    projections = load_h6h7_projections(h6h7_dir)

    h7_final_dir = Path("runs/model_expansion/gemini_flash_h7_val_final")
    projections_final = load_h6h7_projections(h7_final_dir)
    for harness_id, docs in projections_final.items():
        for doc_id, data in docs.items():
            projections.setdefault(harness_id, {})[doc_id] = data

    summaries = {}
    if h0_outputs:
        summaries["H0_strict_canonical"] = score_all("gemini_flash:H0", h0_outputs, gold, schema_path, exect_root)
    for harness_id, outputs in projections.items():
        label = f"gemini_flash:{harness_id}"
        summaries[harness_id] = score_all(label, outputs, gold, schema_path, exect_root)

    # Print table
    fields = [
        "medication_name_f1",
        "medication_full_f1",
        "seizure_type_f1",
        "seizure_type_f1_collapsed",
        "epilepsy_diagnosis_accuracy",
        "epilepsy_diagnosis_accuracy_collapsed",
        "current_seizure_frequency_loose_accuracy",
        "eeg_accuracy",
        "mri_accuracy",
        "temporal_accuracy",
        "schema_valid_rate",
        "quote_validity_rate",
        "documents_available",
    ]

    print(f"{'Harness':<40}", end="")
    for f in fields:
        print(f"{f:<30}", end="")
    print()
    print("=" * (40 + 30 * len(fields)))

    for harness_id, summary in summaries.items():
        print(f"{harness_id:<40}", end="")
        for f in fields:
            val = summary.get(f)
            if val is None:
                s = "N/A"
            elif isinstance(val, float):
                s = f"{val:.3f}"
            else:
                s = str(val)
            print(f"{s:<30}", end="")
        print()

    # Also write JSON
    out_path = Path("runs/model_expansion/gemini_flash_validation_summary.json")
    out_path.write_text(json.dumps(summaries, indent=2, default=str), encoding="utf-8")
    print(f"\nWrote summary to {out_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
