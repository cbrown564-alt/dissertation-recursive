#!/usr/bin/env python3
"""Milestone 2 dataset intake utilities.

The intake layer keeps the first data contract intentionally boring:
documents can be discovered, split deterministically, preprocessed into
sentence-like spans with offsets, paired with BRAT gold labels, and checked for
annotation quote normalization issues.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


DEFAULT_EXECT_ROOT = Path("data/ExECT 2 (2025)/Gold1-200_corrected_spelling")
DEFAULT_MANIFEST = Path("data/manifests/dataset_manifest.json")
DEFAULT_SPLITS = Path("data/splits/exectv2_splits.json")
SPLIT_SALT = "exectv2-fixed-splits-v1"


@dataclass(frozen=True)
class SentenceSpan:
    sentence_id: str
    char_start: int
    char_end: int
    text: str


@dataclass(frozen=True)
class GoldAnnotation:
    id: str
    label: str
    char_start: int
    char_end: int
    annotation_text: str
    source_text: str
    attributes: dict[str, str]
    normalized_match_by_offset: bool
    normalized_match_in_document: bool


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def document_ids(exect_root: Path = DEFAULT_EXECT_ROOT) -> list[str]:
    return sorted(path.stem for path in exect_root.glob("EA*.txt"))


def normalize_source_text(text: str) -> str:
    """Normalize source letter text for model input while preserving content."""
    text = text.replace("\ufeff", "")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return re.sub(r"[ \t]+", " ", text).strip()


def normalize_quote(text: str) -> str:
    """Normalize evidence/span text for conservative quote matching."""
    replacements = {
        "\ufeff": "",
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u2013": "-",
        "\u2014": "-",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    text = text.replace("-", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip().lower()


def split_sentences(text: str) -> list[SentenceSpan]:
    """Split into stable sentence-like spans with source offsets.

    Clinic letters contain headings, medication lists, and short fragments. This
    splitter treats non-empty lines as the first boundary, then separates
    punctuation-ended sentence-like clauses within each line.
    """
    spans: list[SentenceSpan] = []
    line_pattern = re.compile(r"[^\n]+")
    sentence_pattern = re.compile(r".+?(?:[.!?](?=\s+|$)|$)", re.DOTALL)

    for line_match in line_pattern.finditer(text):
        line = line_match.group(0)
        line_start = line_match.start()
        for sentence_match in sentence_pattern.finditer(line):
            raw = sentence_match.group(0)
            leading = len(raw) - len(raw.lstrip())
            trailing = len(raw.rstrip())
            cleaned = raw.strip()
            if not cleaned:
                continue
            start = line_start + sentence_match.start() + leading
            end = line_start + sentence_match.start() + trailing
            spans.append(SentenceSpan(f"s{len(spans) + 1:04d}", start, end, cleaned))
    return spans


def parse_textbound(line: str) -> tuple[str, str, int, int, str] | None:
    parts = line.split("\t")
    if len(parts) < 3 or not parts[0].startswith("T"):
        return None
    metadata = parts[1].split()
    if len(metadata) < 3:
        return None
    label = metadata[0]
    offsets = " ".join(metadata[1:])
    offset_parts = re.split(r"[ ;]+", offsets)
    numbers = [int(part) for part in offset_parts if part.isdigit()]
    if len(numbers) < 2:
        return None
    return parts[0], label, numbers[0], numbers[-1], parts[2]


def parse_attribute(line: str) -> tuple[str, str, str, str] | None:
    parts = line.split("\t")
    if len(parts) < 2 or not parts[0].startswith("A"):
        return None
    metadata = parts[1].split(maxsplit=2)
    if len(metadata) < 2:
        return None
    value = metadata[2] if len(metadata) == 3 else "true"
    return parts[0], metadata[0], metadata[1], value


def load_gold_annotations(document_id: str, exect_root: Path = DEFAULT_EXECT_ROOT) -> list[GoldAnnotation]:
    text = read_text(exect_root / f"{document_id}.txt")
    ann_lines = read_text(exect_root / f"{document_id}.ann").splitlines()
    attributes_by_target: dict[str, dict[str, str]] = {}
    textbounds: list[tuple[str, str, int, int, str]] = []

    for line in ann_lines:
        textbound = parse_textbound(line)
        if textbound is not None:
            textbounds.append(textbound)
            continue
        attribute = parse_attribute(line)
        if attribute is not None:
            _, name, target, value = attribute
            attributes_by_target.setdefault(target, {})[name] = value

    normalized_document = normalize_quote(text)
    annotations = []
    for annotation_id, label, start, end, annotation_text in textbounds:
        source_text = text[start:end]
        normalized_annotation = normalize_quote(annotation_text)
        annotations.append(
            GoldAnnotation(
                id=annotation_id,
                label=label,
                char_start=start,
                char_end=end,
                annotation_text=annotation_text,
                source_text=source_text,
                attributes=attributes_by_target.get(annotation_id, {}),
                normalized_match_by_offset=normalize_quote(source_text) == normalized_annotation,
                normalized_match_in_document=normalized_annotation in normalized_document,
            )
        )
    return annotations


def preprocess_document(document_id: str, exect_root: Path = DEFAULT_EXECT_ROOT) -> dict[str, Any]:
    text_path = exect_root / f"{document_id}.txt"
    source_text = read_text(text_path)
    normalized_text = normalize_source_text(source_text)
    return {
        "document_id": document_id,
        "source_path": str(text_path),
        "text": source_text,
        "normalized_text": normalized_text,
        "sentences": [asdict(span) for span in split_sentences(source_text)],
    }


def fixed_splits(ids: list[str]) -> dict[str, Any]:
    ordered = sorted(ids, key=lambda item: hashlib.sha256(f"{SPLIT_SALT}:{item}".encode()).hexdigest())
    return {
        "name": "exectv2_fixed_v1",
        "method": "sha256(document_id, salt) deterministic 60/20/20 split",
        "salt": SPLIT_SALT,
        "counts": {"development": 120, "validation": 40, "test": 40},
        "development": sorted(ordered[:120]),
        "validation": sorted(ordered[120:160]),
        "test": sorted(ordered[160:]),
    }


def build_manifest(exect_root: Path = DEFAULT_EXECT_ROOT) -> dict[str, Any]:
    ids = document_ids(exect_root)
    gan_path = Path("data/Gan (2026)/synthetic_data_subset_1500.json")
    return {
        "version": "2026-05-06-milestone-2",
        "datasets": {
            "exectv2": {
                "role": "primary",
                "root": "data/ExECT 2 (2025)",
                "letters_dir": str(exect_root),
                "annotation_format": "BRAT standoff .ann plus .txt source letters",
                "document_count": len(ids),
                "documents": ids,
                "annotation_config": str(exect_root / "annotation.conf"),
                "derived_split_file": str(DEFAULT_SPLITS),
            },
            "gan_2026": {
                "role": "auxiliary",
                "root": "data/Gan (2026)",
                "primary_file": str(gan_path),
                "record_count": count_json_records(gan_path),
            },
        },
    }


def count_json_records(path: Path) -> int | None:
    if not path.exists():
        return None
    try:
        data = json.loads(read_text(path))
    except json.JSONDecodeError:
        return None
    if isinstance(data, list):
        return len(data)
    if isinstance(data, dict):
        for key in ["data", "records", "examples"]:
            if isinstance(data.get(key), list):
                return len(data[key])
    return None


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def command_build_artifacts(args: argparse.Namespace) -> int:
    root = Path(args.exect_root)
    write_json(Path(args.manifest), build_manifest(root))
    write_json(Path(args.splits), fixed_splits(document_ids(root)))
    print(f"wrote {args.manifest}")
    print(f"wrote {args.splits}")
    return 0


def command_check_one(args: argparse.Namespace) -> int:
    root = Path(args.exect_root)
    preprocessed = preprocess_document(args.document_id, root)
    annotations = load_gold_annotations(args.document_id, root)
    mismatches = [
        annotation
        for annotation in annotations
        if not annotation.normalized_match_by_offset or not annotation.normalized_match_in_document
    ]
    result = {
        "document_id": args.document_id,
        "sentence_count": len(preprocessed["sentences"]),
        "gold_annotation_count": len(annotations),
        "first_sentence": preprocessed["sentences"][0] if preprocessed["sentences"] else None,
        "first_gold_annotation": asdict(annotations[0]) if annotations else None,
        "quote_normalization": {
            "annotation_count": len(annotations),
            "mismatch_count": len(mismatches),
            "mismatches": [asdict(item) for item in mismatches[: args.max_mismatches]],
        },
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


def command_check_quotes(args: argparse.Namespace) -> int:
    root = Path(args.exect_root)
    summary = {
        "documents": 0,
        "annotations": 0,
        "offset_mismatches": 0,
        "document_mismatches": 0,
        "examples": [],
    }
    for document_id in document_ids(root):
        summary["documents"] += 1
        for annotation in load_gold_annotations(document_id, root):
            summary["annotations"] += 1
            if not annotation.normalized_match_by_offset:
                summary["offset_mismatches"] += 1
            if not annotation.normalized_match_in_document:
                summary["document_mismatches"] += 1
            if (
                len(summary["examples"]) < args.max_examples
                and (not annotation.normalized_match_by_offset or not annotation.normalized_match_in_document)
            ):
                example = asdict(annotation)
                example["document_id"] = document_id
                summary["examples"].append(example)
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exect-root", default=str(DEFAULT_EXECT_ROOT))
    subparsers = parser.add_subparsers(dest="command", required=True)

    build = subparsers.add_parser("build-artifacts", help="Write dataset manifest and fixed split files.")
    build.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    build.add_argument("--splits", default=str(DEFAULT_SPLITS))
    build.set_defaults(func=command_build_artifacts)

    check_one = subparsers.add_parser("check-one", help="Load, preprocess, and pair one letter with gold labels.")
    check_one.add_argument("document_id")
    check_one.add_argument("--max-mismatches", type=int, default=5)
    check_one.set_defaults(func=command_check_one)

    check_quotes = subparsers.add_parser("check-quotes", help="Summarize ExECTv2 quote-normalization mismatches.")
    check_quotes.add_argument("--max-examples", type=int, default=10)
    check_quotes.set_defaults(func=command_check_quotes)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
