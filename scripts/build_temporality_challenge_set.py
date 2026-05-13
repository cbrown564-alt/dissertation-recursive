#!/usr/bin/env python3
"""Build a temporality challenge set from ExECTv2 letters."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from core.io import write_csv, write_json, write_text
from core.temporality_challenge import summarize_temporality_rows, temporality_matches
from direct_baselines import load_split_ids
from intake import DEFAULT_EXECT_ROOT, DEFAULT_SPLITS, preprocess_document


def markdown_summary(summary: dict[str, object]) -> str:
    lines = [
        "# Temporality Challenge Set",
        "",
        f"Documents with matches: {summary.get('documents_with_matches', 0)}",
        f"Total matches: {summary.get('match_count', 0)}",
        "",
        "## Categories",
    ]
    categories = summary.get("categories") or {}
    if isinstance(categories, dict):
        for category, counts in sorted(categories.items()):
            if isinstance(counts, dict):
                lines.append(f"- {category}: {counts.get('matches', 0)} matches across {counts.get('documents', 0)} documents")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exect-root", default=str(DEFAULT_EXECT_ROOT))
    parser.add_argument("--splits", default=str(DEFAULT_SPLITS))
    parser.add_argument("--split", default="validation", choices=["development", "validation", "test"])
    parser.add_argument("--limit", type=int)
    parser.add_argument("--output-dir", default="runs/temporality_challenge_set")
    args = parser.parse_args()

    document_ids = load_split_ids(Path(args.splits), args.split, args.limit)
    rows = []
    for document_id in document_ids:
        document = preprocess_document(document_id, Path(args.exect_root))
        rows.extend(temporality_matches(document_id, document["text"]))

    summary = summarize_temporality_rows(rows)
    summary["split"] = args.split
    summary["source_document_count"] = len(document_ids)
    summary["document_ids"] = sorted({row["document_id"] for row in rows})

    output_dir = Path(args.output_dir)
    write_csv(output_dir / "temporality_challenge_rows.csv", rows)
    write_json(output_dir / "temporality_challenge_summary.json", summary)
    write_text(output_dir / "temporality_challenge_summary.md", markdown_summary(summary))
    print(f"wrote {len(rows)} temporality matches across {summary['documents_with_matches']} documents to {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
