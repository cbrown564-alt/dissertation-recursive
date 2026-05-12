#!/usr/bin/env python3
"""Archived robustness mini-run for the evidence resolver.

Retained for historical reproduction and targeted perturbation checks. New
scored local-candidate runs should use
``scripts/run_evidence_resolver_scored_batch.py``.

Applies family_history_trap and negated_investigation_trap to validation
documents, runs the evidence resolver, and checks whether any evidence quotes
are drawn from the perturbed (irrelevant) sections.

Usage:
    python scripts/run_evidence_resolver_robustness.py --limit 10
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from evidence_resolver import (
    ResolverStats,
    collect_resolvable_values,
    deterministic_resolve,
    resolve_evidence_hybrid,
)
from intake import preprocess_document
from robustness import add_family_history_trap, add_negated_investigation
from validate_extraction import check_quote_validity


ARCHIVAL_STATUS = "archived_pilot_runner"
MAINTAINED_ENTRYPOINT = "scripts/run_evidence_resolver_scored_batch.py"


def load_split_ids(splits_path: Path, split_name: str, limit: int | None = None) -> list[str]:
    splits = json.loads(splits_path.read_text(encoding="utf-8"))
    ids = splits.get(split_name, [])
    if limit:
        ids = ids[:limit]
    return ids


def run_robustness(args: argparse.Namespace) -> int:
    canonical_dir = Path(args.canonical_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    doc_ids = load_split_ids(Path(args.splits), args.split, args.limit)

    all_stats: list[dict] = []

    for doc_id in doc_ids:
        canonical_path = canonical_dir / doc_id / "canonical_projection.json"
        if not canonical_path.exists():
            print(f"skip {doc_id}: no canonical projection")
            continue

        canonical = json.loads(canonical_path.read_text(encoding="utf-8"))
        document = preprocess_document(doc_id, Path(args.exect_root))
        source_text = document["text"]

        for perturb_name, perturb_fn in (
            ("family_history_trap", add_family_history_trap),
            ("negated_investigation_trap", add_negated_investigation),
        ):
            perturbed_text = perturb_fn(source_text, doc_id)
            trap_text = perturbed_text[len(source_text):]

            resolved, stats = resolve_evidence_hybrid(
                canonical,
                perturbed_text,
                model_call=None,  # deterministic only for robustness test
                expand_sentence=True,
            )

            # Check if any evidence quote is from the trap section
            trap_quotes: list[tuple[str, str]] = []
            for value in collect_resolvable_values(resolved):
                result = deterministic_resolve(perturbed_text, value, expand_sentence=True)
                if result and result.quote:
                    # Check if the quote overlaps with the trap section
                    quote_start = perturbed_text.find(result.quote)
                    trap_start = perturbed_text.find(trap_text)
                    if quote_start >= 0 and trap_start >= 0:
                        quote_end = quote_start + len(result.quote)
                        trap_end = trap_start + len(trap_text)
                        if quote_start < trap_end and quote_end > trap_start:
                            trap_quotes.append((value.path, result.quote))

            total, failures = check_quote_validity(resolved, perturbed_text)

            report = {
                "document_id": doc_id,
                "perturbation": perturb_name,
                "trap_text": trap_text.strip(),
                "total_values": stats.total_values,
                "deterministic_hits": stats.deterministic_hits,
                "ungrounded": stats.ungrounded,
                "trap_quotes": trap_quotes,
                "trap_quote_count": len(trap_quotes),
                "quote_validity_rate": (total - len(failures)) / total if total else 1.0,
                "invalid_quote_paths": failures,
            }
            all_stats.append(report)

            status = "PASS" if not trap_quotes and not failures else "FAIL"
            print(
                f"{doc_id} {perturb_name}: {status} "
                f"det={stats.deterministic_hits} ung={stats.ungrounded} "
                f"trap_quotes={len(trap_quotes)} invalid={len(failures)}"
            )

    summary_path = output_dir / "robustness_report.json"
    summary_path.write_text(json.dumps(all_stats, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    total_trap_quotes = sum(r["trap_quote_count"] for r in all_stats)
    total_invalid = sum(len(r["invalid_quote_paths"]) for r in all_stats)
    print("=" * 60)
    print("Robustness Mini-Run Summary")
    print("=" * 60)
    print(f"Document-perturbation pairs: {len(all_stats)}")
    print(f"Trap quotes (hallucinated):  {total_trap_quotes}")
    print(f"Invalid quotes:              {total_invalid}")
    print(f"Wrote: {summary_path}")
    return 1 if total_trap_quotes > 0 or total_invalid > 0 else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--canonical-dir",
        default="runs/local_models/stage_l5_35b_full/calls/qwen_35b_local/H6fs_benchmark_only_coarse_json",
    )
    parser.add_argument("--output-dir", default="runs/evidence_resolver/robustness")
    parser.add_argument("--splits", default="data/splits/exectv2_splits.json")
    parser.add_argument("--split", default="validation")
    parser.add_argument("--exect-root", default="data/ExECT 2 (2025)/Gold1-200_corrected_spelling")
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args()
    return run_robustness(args)


if __name__ == "__main__":
    raise SystemExit(main())
