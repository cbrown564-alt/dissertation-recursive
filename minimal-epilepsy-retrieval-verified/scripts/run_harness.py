from __future__ import annotations

import argparse
import json
import sys
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from epilepsy_extraction.data import compute_file_sha256, load_synthetic_subset, select_fixed_slice
from epilepsy_extraction.harnesses import (
    attach_manifest_to_run,
    default_manifest_path,
    load_harness_manifest,
    run_clines_epilepsy_modular,
    run_clines_epilepsy_verified,
    run_retrieval_field_extractors,
)
from epilepsy_extraction.providers import OpenAIProvider, ReplayProvider
from epilepsy_extraction.schemas import DatasetSlice, RunStatus, resolve_code_version, write_run_record


def _load_row_ids(path: Path | None) -> list[str] | None:
    if path is None:
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        data = data.get("row_ids", [])
    return [str(item) for item in data]


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the minimal retrieval/verified epilepsy extraction harnesses.")
    parser.add_argument("dataset", type=Path)
    parser.add_argument(
        "--harness",
        choices=["retrieval_field_extractors", "clines_epilepsy_modular", "clines_epilepsy_verified"],
        required=True,
    )
    parser.add_argument("--row-ids", type=Path, default=Path("data/selected_rows_n25.json"))
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--provider", choices=["replay", "openai"], default="replay")
    parser.add_argument("--replay", type=Path, default=None)
    parser.add_argument("--model", default="gpt-5.5-2026-04-23")
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--code-version", default=None)
    parser.add_argument("--status", choices=[item.value for item in RunStatus], default=RunStatus.CANONICAL.value)
    parser.add_argument("--model-registry-entry", default=None)
    args = parser.parse_args()

    manifest_path = default_manifest_path(args.harness, Path.cwd())
    manifest = load_harness_manifest(manifest_path) if manifest_path.exists() else None

    def make_provider():
        if args.provider == "openai":
            return OpenAIProvider()
        if args.replay is None:
            raise SystemExit("--replay is required with --provider=replay")
        return ReplayProvider(args.replay)

    records = load_synthetic_subset(args.dataset)
    row_ids = _load_row_ids(args.row_ids) if args.row_ids and args.row_ids.exists() else None
    selected = select_fixed_slice(records, row_ids=row_ids, limit=args.limit)
    dataset = DatasetSlice(
        dataset_id=args.dataset.stem,
        dataset_path=str(args.dataset),
        data_hash=compute_file_sha256(args.dataset),
        row_ids=[record.row_id for record in selected],
        inclusion_criteria=f"row_ok_only=true; row_ids={bool(row_ids)}; limit={args.limit}",
    )
    code_version = resolve_code_version(args.code_version, cwd=Path.cwd(), fallback="uncommitted")

    runner = {
        "retrieval_field_extractors": run_retrieval_field_extractors,
        "clines_epilepsy_modular": run_clines_epilepsy_modular,
        "clines_epilepsy_verified": run_clines_epilepsy_verified,
    }[args.harness]
    record = runner(
        selected,
        dataset,
        args.run_id,
        code_version,
        make_provider(),
        model=args.model,
        temperature=args.temperature,
    )
    record = replace(
        record,
        status=RunStatus(args.status),
        model_registry_entry=args.model_registry_entry or args.model,
    )
    record = attach_manifest_to_run(record, manifest)
    write_run_record(record, args.output)
    print(json.dumps({"run_id": args.run_id, "rows": len(selected), "output": str(args.output)}, indent=2))


if __name__ == "__main__":
    main()
