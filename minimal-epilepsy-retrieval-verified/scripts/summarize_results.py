from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from epilepsy_extraction.evaluation.tables import build_result_tables, load_run_records, write_result_tables


def _load_adjudication_accuracy(path: Path) -> dict[str, dict[str, float]]:
    """Return {run_id: {field_family: exact_accuracy}} from a completed adjudication CSV."""
    scores: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            score = str(row.get("value_score", "")).strip()
            if score:
                scores[row["run_id"]][row["field_family"]].append(score)
    result: dict[str, dict[str, float]] = {}
    for run_id, families in scores.items():
        result[run_id] = {}
        for fam, vals in families.items():
            if vals:
                result[run_id][fam] = sum(1 for v in vals if v == "1") / len(vals)
    return result


def _patch_field_level_correctness(
    table_rows: list[dict],
    accuracy: dict[str, dict[str, float]],
) -> list[dict]:
    """Merge adjudication accuracy into field_level_correctness rows."""
    patched = []
    for row in table_rows:
        run_id = row.get("run_id", "")
        fam = row.get("field_family", "")
        if run_id in accuracy and fam in accuracy[run_id]:
            row = dict(row)
            row["exact_label_accuracy"] = round(accuracy[run_id][fam], 4)
            row["adjudication_status"] = "auto_adjudicated"
        patched.append(row)
    return patched


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarize run records and generate result tables.")
    parser.add_argument("run_record", type=Path, nargs="+")
    parser.add_argument(
        "--tables-dir",
        type=Path,
        default=None,
        help="Write Phase 9 JSON/CSV result tables to this directory.",
    )
    parser.add_argument(
        "--model-registry",
        type=Path,
        default=None,
        help="Optional model registry YAML used to populate model-family tables.",
    )
    parser.add_argument(
        "--adjudication",
        type=Path,
        action="append",
        default=None,
        help="Completed adjudication CSV(s) to merge into field_level_correctness. Repeat for multiple files; later files override earlier ones for the same run/field.",
    )
    args = parser.parse_args()

    records = load_run_records(args.run_record)
    if args.tables_dir is not None:
        tables = build_result_tables(records, model_registry_path=args.model_registry)
        if args.adjudication:
            merged: dict[str, dict[str, float]] = {}
            for adj_path in args.adjudication:
                if adj_path.exists():
                    for run_id, fams in _load_adjudication_accuracy(adj_path).items():
                        merged.setdefault(run_id, {}).update(fams)
            if merged:
                tables["field_level_correctness"] = _patch_field_level_correctness(
                    tables["field_level_correctness"], merged
                )
        written = write_result_tables(tables, args.tables_dir)
        summary = {
            "run_records": len(records),
            "tables_dir": str(args.tables_dir),
            "tables": sorted({path.stem for path in written}),
            "files_written": [str(path) for path in written],
        }
        print(json.dumps(summary, indent=2, sort_keys=True))
        return

    data = records[0]
    summary = {
        "run_id": data["run_id"],
        "harness": data["harness"],
        "status": data["status"],
        "n": data["dataset"]["n"],
        "provider": data["provider"],
        "model": data["model"],
        "warnings": data["warnings"],
    }
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
