"""Run the curated local/open h008 guarded broader-field harness."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from run_broader_field_experiment import main


if __name__ == "__main__":
    raise SystemExit(
        main(
            [
                "--harness",
                "h008",
                "--provider",
                "ollama",
                "--model",
                "qwen3.5:4b",
                "--data",
                "data/synthetic_data_subset_1500.json",
                "--limit",
                "50",
                "--timeout-seconds",
                "180",
                "--max-retries",
                "1",
                "--adjudication-csv",
                "docs/adjudication/h008_guideline_matched_25rows_scoring.csv",
                *sys.argv[1:],
            ]
        )
    )
