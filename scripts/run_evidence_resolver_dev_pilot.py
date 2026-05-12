#!/usr/bin/env python3
"""Archived dev-pilot for the Option-C hybrid evidence resolver.

Retained for historical reproduction. New scored evidence-resolver runs should
use ``scripts/run_evidence_resolver_scored_batch.py``.

Usage:
    python scripts/run_evidence_resolver_dev_pilot.py \
        --canonical-dir runs/local_models/stage_l5_35b_full/calls/qwen_35b_local/H6fs_benchmark_only_coarse_json \
        --output-dir runs/evidence_resolver/dev_pilot_qwen35b_h6fs \
        --limit 10

Reads existing H6fs canonical projections, runs the deterministic evidence
resolver (Pass 2a), and reports aggregate metrics.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from evidence_resolver import ResolverStats, resolve_evidence_hybrid
from intake import DEFAULT_EXECT_ROOT, preprocess_document
from validate_extraction import check_quote_validity


ARCHIVAL_STATUS = "archived_pilot_runner"
MAINTAINED_ENTRYPOINT = "scripts/run_evidence_resolver_scored_batch.py"


def load_canonical(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def run_dev_pilot(args: argparse.Namespace) -> int:
    canonical_dir = Path(args.canonical_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load validation split IDs
    splits_path = Path(args.splits)
    splits = json.loads(splits_path.read_text(encoding="utf-8"))
    doc_ids = splits.get("validation", [])
    if args.limit:
        doc_ids = doc_ids[: args.limit]

    all_stats: list[ResolverStats] = []
    per_doc_reports: list[dict] = []
    total_quote_count = 0
    total_valid_quotes = 0
    total_present_fields = 0
    total_with_evidence = 0

    for doc_id in doc_ids:
        canonical_path = canonical_dir / doc_id / "canonical_projection.json"
        if not canonical_path.exists():
            print(f"skip {doc_id}: no canonical projection at {canonical_path}")
            continue

        canonical = load_canonical(canonical_path)
        document = preprocess_document(doc_id, Path(args.exect_root))
        source_text = document["text"]

        resolved, stats = resolve_evidence_hybrid(
            canonical,
            source_text,
            model_call=None,
            expand_sentence=True,
        )

        quote_total, quote_failures = check_quote_validity(resolved, source_text)
        valid_quotes = quote_total - len(quote_failures)

        # Count present fields and evidence presence
        fields = resolved.get("fields", {})
        present_count = 0
        with_evidence_count = 0
        for key, field in fields.items():
            if isinstance(field, list):
                for item in field:
                    if isinstance(item, dict) and item.get("missingness") == "present":
                        present_count += 1
                        if item.get("evidence"):
                            with_evidence_count += 1
            elif isinstance(field, dict) and field.get("missingness") == "present":
                present_count += 1
                if field.get("evidence"):
                    with_evidence_count += 1

        total_quote_count += quote_total
        total_valid_quotes += valid_quotes
        total_present_fields += present_count
        total_with_evidence += with_evidence_count

        all_stats.append(stats)
        per_doc_reports.append(
            {
                "document_id": doc_id,
                "stats": stats.to_dict(),
                "quote_count": quote_total,
                "valid_quotes": valid_quotes,
                "invalid_quote_paths": quote_failures,
                "present_fields": present_count,
                "fields_with_evidence": with_evidence_count,
            }
        )

        # Write resolved canonical
        doc_out = output_dir / "resolved" / f"{doc_id}.json"
        doc_out.parent.mkdir(parents=True, exist_ok=True)
        doc_out.write_text(json.dumps(resolved, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    # Aggregate
    if not all_stats:
        print("No documents processed.")
        return 1

    total_values = sum(s.total_values for s in all_stats)
    deterministic_hits = sum(s.deterministic_hits for s in all_stats)
    fallback_hits = sum(s.fallback_hits for s in all_stats)
    ungrounded = sum(s.ungrounded for s in all_stats)

    aggregate = {
        "documents_processed": len(all_stats),
        "total_values": total_values,
        "deterministic_hits": deterministic_hits,
        "fallback_hits": fallback_hits,
        "ungrounded": ungrounded,
        "fallback_rate": round(fallback_hits / total_values, 4) if total_values else 0.0,
        "ungrounded_rate": round(ungrounded / total_values, 4) if total_values else 0.0,
        "quote_presence_rate": round(total_with_evidence / total_present_fields, 4) if total_present_fields else 0.0,
        "quote_validity_rate": round(total_valid_quotes / total_quote_count, 4) if total_quote_count else 0.0,
        "total_present_fields": total_present_fields,
        "total_fields_with_evidence": total_with_evidence,
        "total_quotes": total_quote_count,
        "total_valid_quotes": total_valid_quotes,
        "per_document": per_doc_reports,
    }

    summary_path = output_dir / "aggregate_report.json"
    summary_path.write_text(json.dumps(aggregate, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print("=" * 60)
    print("Evidence Resolver Dev-Pilot (Option C — deterministic only)")
    print("=" * 60)
    print(f"Documents processed: {aggregate['documents_processed']}")
    print(f"Total values:        {aggregate['total_values']}")
    print(f"Deterministic hits:  {aggregate['deterministic_hits']}")
    print(f"Fallback hits:       {aggregate['fallback_hits']}")
    print(f"Ungrounded:          {aggregate['ungrounded']}")
    print(f"Fallback rate:       {aggregate['fallback_rate']:.4f}")
    print(f"Ungrounded rate:     {aggregate['ungrounded_rate']:.4f}")
    print(f"Quote presence:      {aggregate['quote_presence_rate']:.4f} ({aggregate['total_fields_with_evidence']}/{aggregate['total_present_fields']})")
    print(f"Quote validity:      {aggregate['quote_validity_rate']:.4f} ({aggregate['total_valid_quotes']}/{aggregate['total_quotes']})")
    print(f"Wrote:               {summary_path}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--canonical-dir",
        default="runs/local_models/stage_l5_35b_full/calls/qwen_35b_local/H6fs_benchmark_only_coarse_json",
        help="Directory containing canonical_projection.json per document.",
    )
    parser.add_argument(
        "--output-dir",
        default="runs/evidence_resolver/dev_pilot_qwen35b_h6fs",
        help="Where to write resolved extractions and aggregate report.",
    )
    parser.add_argument("--splits", default="data/splits/exectv2_splits.json")
    parser.add_argument("--exect-root", default=str(DEFAULT_EXECT_ROOT))
    parser.add_argument("--limit", type=int, default=10, help="Number of validation docs to process.")
    args = parser.parse_args()
    return run_dev_pilot(args)


if __name__ == "__main__":
    raise SystemExit(main())
