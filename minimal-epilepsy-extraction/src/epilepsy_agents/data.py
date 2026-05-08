from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from .schema import GoldRecord


def load_synthetic_subset(path: str | Path) -> list[GoldRecord]:
    """Load Gan et al. synthetic subset records from the released JSON shape."""
    with Path(path).open("r", encoding="utf-8") as handle:
        rows = json.load(handle)

    records: list[GoldRecord] = []
    for row in rows:
        check = row["check__Seizure Frequency Number"]
        label, evidence = check["seizure_frequency_number"]
        records.append(
            GoldRecord(
                source_row_index=int(row["source_row_index"]),
                letter=row["clinic_date"],
                gold_label=label,
                gold_evidence=evidence,
                row_ok=bool(row.get("row_ok", False)),
                raw=row,
            )
        )
    return records


def iter_records(
    records: Iterable[GoldRecord], limit: int | None = None, row_ok_only: bool = True
) -> Iterable[GoldRecord]:
    seen = 0
    for record in records:
        if limit is not None and seen >= limit:
            return
        if row_ok_only and not record.row_ok:
            continue
        yield record
        seen += 1
