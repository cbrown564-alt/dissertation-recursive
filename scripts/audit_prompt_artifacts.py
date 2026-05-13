#!/usr/bin/env python3
"""Audit maintained extraction prompts for internal run artefacts."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Callable

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from core.prompts import build_h6_prompt, build_h6fs_prompt, build_h6full_prompt, prompt_artifact_report
from direct_baselines import write_json
from intake import DEFAULT_EXECT_ROOT, preprocess_document

PROMPT_BUILDERS: dict[str, Callable[[dict[str, Any], str, str], str]] = {
    "H6_benchmark_only_coarse_json": build_h6_prompt,
    "H6fs_benchmark_only_coarse_json": build_h6fs_prompt,
    "H6full_benchmark_coarse_json": build_h6full_prompt,
}


def audit_prompts(document_id: str, exect_root: Path) -> list[dict[str, Any]]:
    document = preprocess_document(document_id, exect_root)
    rows: list[dict[str, Any]] = []
    for harness_id, builder in PROMPT_BUILDERS.items():
        for prompt_style in ["internal", "clinician"]:
            prompt = builder(document, harness_id, prompt_style)
            report = prompt_artifact_report(prompt, harness_id)
            rows.append(
                {
                    "document_id": document_id,
                    "harness_id": harness_id,
                    "prompt_style": prompt_style,
                    **report,
                    "prompt_chars": len(prompt),
                }
            )
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--document-id", default="EA0001")
    parser.add_argument("--exect-root", default=str(DEFAULT_EXECT_ROOT))
    parser.add_argument("--output", default="runs/prompt_artifact_audit/prompt_artifacts.json")
    args = parser.parse_args()

    rows = audit_prompts(args.document_id, Path(args.exect_root))
    write_json(
        Path(args.output),
        {
            "document_id": args.document_id,
            "prompt_styles": ["internal", "clinician"],
            "rows": rows,
        },
    )
    print(f"wrote {len(rows)} prompt artifact rows to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
