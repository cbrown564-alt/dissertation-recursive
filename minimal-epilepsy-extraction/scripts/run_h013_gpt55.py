"""Run the curated closed/frontier h013 production harness."""
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
                "h013",
                "--provider",
                "openai",
                "--model",
                "gpt-5.5",
                "--data",
                "data/synthetic_data_subset_1500.json",
                "--limit",
                "50",
                "--timeout-seconds",
                "240",
                "--max-retries",
                "1",
                "--adjudication-csv",
                "docs/adjudication/h013_gpt55_matched_25rows_scoring.csv",
                *sys.argv[1:],
            ]
        )
    )
