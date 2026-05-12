"""Dataset-oriented helpers that are stable across experiment phases."""

from __future__ import annotations

from pathlib import Path

from .io import read_json


def load_split_ids(split_path: Path, split: str, limit: int | None = None) -> list[str]:
    split_data = read_json(split_path)
    if split not in split_data:
        raise KeyError(f"unknown split {split!r} in {split_path}")
    ids = list(split_data[split])
    return ids[:limit] if limit is not None else ids

