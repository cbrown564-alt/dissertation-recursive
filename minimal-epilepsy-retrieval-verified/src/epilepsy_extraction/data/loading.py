from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from pathlib import Path

from epilepsy_extraction.schemas import GoldRecord


def compute_file_sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_synthetic_subset(path: str | Path) -> list[GoldRecord]:
    """Load the released synthetic subset shape used by the exploration repo."""
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
    records: Iterable[GoldRecord],
    limit: int | None = None,
    row_ok_only: bool = True,
) -> Iterable[GoldRecord]:
    if limit is not None and limit <= 0:
        return

    seen = 0
    for record in records:
        if row_ok_only and not record.row_ok:
            continue
        if limit is not None and seen >= limit:
            return
        yield record
        seen += 1


def select_fixed_slice(
    records: Iterable[GoldRecord],
    row_ids: Iterable[str] | None = None,
    limit: int | None = None,
    row_ok_only: bool = True,
) -> list[GoldRecord]:
    selected_ids = set(row_ids) if row_ids is not None else None
    filtered = iter_records(records, limit=None, row_ok_only=row_ok_only)

    selected: list[GoldRecord] = []
    for record in filtered:
        if selected_ids is not None and record.row_id not in selected_ids:
            continue
        selected.append(record)
        if limit is not None and len(selected) >= limit:
            break
    return selected
