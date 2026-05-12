#!/usr/bin/env python3
"""Contract tests for the maintained H6fs evidence-resolver scored runner."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from run_evidence_resolver_scored_batch import run_scored_batch, validate_scored_output_shape


def test_scored_runner_writes_canonical_output_shape(tmp_path: Path) -> None:
    candidates = [
        Path(
            "runs/final_full_field/validation/imported/qwen_35b_local/"
            "H6fs_benchmark_only_coarse_json"
        ),
        Path(
            "runs/local_models/stage_l5_35b_full/calls/qwen_35b_local/"
            "H6fs_benchmark_only_coarse_json"
        ),
    ]
    canonical_dir = next(
        (
            path
            for path in candidates
            if (path / "EA0008" / "canonical_projection.json").exists()
        ),
        None,
    )
    assert canonical_dir is not None, "representative H6fs canonical run artifact is required"

    args = argparse.Namespace(
        canonical_dir=str(canonical_dir),
        output_dir=str(tmp_path),
        splits="data/splits/exectv2_splits.json",
        split="validation",
        exect_root="data/ExECT 2 (2025)/Gold1-200_corrected_spelling",
        markup_root="data/ExECT 2 (2025)/MarkupOutput_200_SyntheticEpilepsyLetters",
        schema="schemas/canonical_extraction.schema.json",
        limit=1,
        fallback=False,
        model="qwen3.6:35b",
    )

    assert run_scored_batch(args) == 0
    contract = validate_scored_output_shape(tmp_path)

    assert contract["report"]["documents"] == 1
    assert contract["manifest"]["pipeline_id"] == "h6fs_option_c_evidence_resolver"
    assert len(contract["resolved_files"]) == 1
