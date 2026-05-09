from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from epilepsy_extraction.evaluation.adjudication import (
    build_adjudication_rows,
    load_run_records,
    write_adjudication_sheet,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a reviewer-facing adjudication CSV from run records.")
    parser.add_argument("run_record", type=Path, nargs="+")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("results/adjudication/adjudication_sheet.csv"),
    )
    args = parser.parse_args()

    records = load_run_records(args.run_record)
    rows = build_adjudication_rows(records)
    output = write_adjudication_sheet(rows, args.output)
    print(
        json.dumps(
            {
                "run_records": len(records),
                "rows": len(rows),
                "output": str(output),
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
