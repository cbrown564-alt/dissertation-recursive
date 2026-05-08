#!/usr/bin/env python3
"""Gan 2026 seizure-frequency benchmark helpers.

The paper reports micro-F1 after mapping normalized frequency labels to
category schemes, not exact string accuracy. This module implements that
benchmark-shaped layer for the released synthetic subset in this repository.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from intake import read_text


DEFAULT_GAN_PATH = Path("data/Gan (2026)/synthetic_data_subset_1500.json")
DEFAULT_OUTPUT_DIR = Path("runs/gan_frequency")
UNKNOWN_X = 1000.0
MULTIPLE_VALUE = 2.0


@dataclass(frozen=True)
class GanExample:
    document_id: str
    source_row_index: int
    text: str
    gold_label: str
    evidence_reference: str
    analysis: str


def normalize_label(value: Any) -> str:
    text = "" if value is None else str(value)
    text = text.strip().lower().replace("-", " ")
    text = re.sub(r"\s+", " ", text)
    return text


def load_gan_examples(path: Path = DEFAULT_GAN_PATH) -> list[GanExample]:
    data = json.loads(read_text(path))
    if not isinstance(data, list):
        raise ValueError(f"Gan data must be a JSON list: {path}")
    examples: list[GanExample] = []
    for row in data:
        if not isinstance(row, dict):
            continue
        label_block = row.get("check__Seizure Frequency Number")
        if not isinstance(label_block, dict):
            continue
        labels = label_block.get("seizure_frequency_number")
        if not (isinstance(labels, list) and labels):
            continue
        reference = label_block.get("reference")
        evidence = reference[1] if isinstance(reference, list) and len(reference) > 1 else ""
        source_row_index = int(row.get("source_row_index", len(examples)))
        examples.append(
            GanExample(
                document_id=f"GAN{source_row_index}",
                source_row_index=source_row_index,
                text=str(row.get("clinic_date") or ""),
                gold_label=normalize_label(labels[0]),
                evidence_reference=str(evidence or ""),
                analysis=str(label_block.get("analysis") or ""),
            )
        )
    return examples


def parse_quantity(value: str) -> float | None:
    value = normalize_label(value)
    if not value:
        return None
    if value in {"a", "an", "one"}:
        return 1.0
    if value == "multiple":
        return MULTIPLE_VALUE
    number_words = {
        "two": 2,
        "three": 3,
        "four": 4,
        "five": 5,
        "six": 6,
        "seven": 7,
        "eight": 8,
        "nine": 9,
        "ten": 10,
    }
    if value in number_words:
        return float(number_words[value])
    if " to " in value:
        parts = [parse_quantity(part) for part in value.split(" to ", 1)]
        if all(part is not None for part in parts):
            return sum(part for part in parts if part is not None) / 2
    try:
        return float(value)
    except ValueError:
        return None


def monthly_factor(unit: str) -> float | None:
    unit = unit.rstrip("s")
    if unit == "day":
        return 30.0
    if unit == "week":
        return 4.0
    if unit == "month":
        return 1.0
    if unit == "year":
        return 1.0 / 12.0
    return None


def rate_to_monthly(count: str, period_count: str, unit: str) -> float | None:
    numerator = parse_quantity(count)
    denominator = parse_quantity(period_count) if period_count else 1.0
    factor = monthly_factor(unit)
    if numerator is None or denominator in {None, 0.0} or factor is None:
        return None
    return numerator * factor / denominator


def label_to_monthly_frequency(label: str) -> float:
    label = normalize_label(label)
    if not label or label in {"unknown", "no seizure frequency reference"}:
        return UNKNOWN_X
    if label.startswith("seizure free") or label in {"no seizure", "no seizures"}:
        return 0.0

    cluster = re.fullmatch(
        r"(.+?) cluster per (?:(.+?) )?(day|week|month|year), (.+?) per cluster",
        label,
    )
    if cluster:
        clusters_per_month = rate_to_monthly(cluster.group(1), cluster.group(2) or "1", cluster.group(3))
        per_cluster = parse_quantity(cluster.group(4))
        if clusters_per_month is not None and per_cluster is not None:
            return clusters_per_month * per_cluster

    rate = re.fullmatch(r"(.+?) per (?:(.+?) )?(day|week|month|year)", label)
    if rate:
        monthly = rate_to_monthly(rate.group(1), rate.group(2) or "1", rate.group(3))
        if monthly is not None:
            return monthly

    return UNKNOWN_X


def purist_category_from_x(x: float) -> str:
    if x == UNKNOWN_X:
        return "UNK"
    if x == 0:
        return "NS"
    if 0 < x <= 0.16:
        return "<1/6M"
    if 0.16 < x <= 0.18:
        return "1/6M"
    if 0.18 < x <= 0.99:
        return "(1/6M,1/M)"
    if 0.99 < x <= 1.1:
        return "1/M"
    if 1.1 < x <= 3.9:
        return "(1/M,1/W)"
    if 3.9 < x <= 4.1:
        return "1/W"
    if 4.1 < x <= 29:
        return "(1/W,1/D)"
    if 29 < x <= 999:
        return ">=1/D"
    return "UNK"


def pragmatic_category_from_x(x: float) -> str:
    if x == UNKNOWN_X:
        return "UNK"
    if x == 0:
        return "NS"
    if 0 < x <= 1.1:
        return "infrequent"
    if 1.1 < x <= 999:
        return "frequent"
    return "UNK"


def label_to_categories(label: str) -> dict[str, Any]:
    x = label_to_monthly_frequency(label)
    return {
        "label": normalize_label(label),
        "x_per_month": x,
        "purist": purist_category_from_x(x),
        "pragmatic": pragmatic_category_from_x(x),
    }


def classification_report(gold: list[str], predicted: list[str]) -> dict[str, Any]:
    labels = sorted(set(gold) | set(predicted))
    rows = []
    total_correct = 0
    total = len(gold)
    weighted_f1 = 0.0
    for label in labels:
        tp = sum(1 for g, p in zip(gold, predicted) if g == label and p == label)
        fp = sum(1 for g, p in zip(gold, predicted) if g != label and p == label)
        fn = sum(1 for g, p in zip(gold, predicted) if g == label and p != label)
        support = sum(1 for g in gold if g == label)
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        total_correct += tp
        weighted_f1 += f1 * support
        rows.append(
            {
                "class": label,
                "precision": precision,
                "recall": recall,
                "f1": f1,
                "support": support,
            }
        )
    macro_f1 = sum(row["f1"] for row in rows) / len(rows) if rows else 0.0
    micro_f1 = total_correct / total if total else 0.0
    return {
        "micro_f1": micro_f1,
        "accuracy": micro_f1,
        "macro_f1": macro_f1,
        "weighted_f1": weighted_f1 / total if total else 0.0,
        "support": total,
        "classes": rows,
    }


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def command_audit(args: argparse.Namespace) -> int:
    examples = load_gan_examples(Path(args.gan_path))
    rows = []
    for example in examples:
        categories = label_to_categories(example.gold_label)
        rows.append(
            {
                "document_id": example.document_id,
                "source_row_index": example.source_row_index,
                "gold_label": example.gold_label,
                "x_per_month": categories["x_per_month"],
                "purist": categories["purist"],
                "pragmatic": categories["pragmatic"],
                "evidence_reference": example.evidence_reference,
            }
        )
    output_dir = Path(args.output_dir)
    write_csv(output_dir / "gan_gold_labels.csv", rows)
    summary = {
        "documents": len(rows),
        "unique_gold_labels": len({row["gold_label"] for row in rows}),
        "purist_distribution": count_values(row["purist"] for row in rows),
        "pragmatic_distribution": count_values(row["pragmatic"] for row in rows),
        "notes": {
            "multiple_value_assumption": MULTIPLE_VALUE,
            "unknown_x_per_month": UNKNOWN_X,
            "primary_paper_metric": "micro-F1 over Purist and Pragmatic category mappings; the ~0.85 target refers to Pragmatic micro-F1 on Real(300), not exact normalized-label accuracy.",
        },
    }
    write_json(output_dir / "gan_gold_audit.json", summary)
    print(f"wrote {output_dir / 'gan_gold_labels.csv'}")
    print(f"wrote {output_dir / 'gan_gold_audit.json'}")
    return 0


def count_values(values: Any) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        counts[str(value)] = counts.get(str(value), 0) + 1
    return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))


def command_evaluate(args: argparse.Namespace) -> int:
    examples = {example.document_id: example for example in load_gan_examples(Path(args.gan_path))}
    predictions = json.loads(read_text(Path(args.predictions)))
    if not isinstance(predictions, dict):
        raise ValueError("predictions must be a JSON object keyed by GAN document_id")
    rows = []
    gold_purist: list[str] = []
    pred_purist: list[str] = []
    gold_pragmatic: list[str] = []
    pred_pragmatic: list[str] = []
    for document_id, predicted_label in predictions.items():
        if document_id not in examples:
            continue
        example = examples[document_id]
        gold_categories = label_to_categories(example.gold_label)
        pred_categories = label_to_categories(str(predicted_label))
        gold_purist.append(gold_categories["purist"])
        pred_purist.append(pred_categories["purist"])
        gold_pragmatic.append(gold_categories["pragmatic"])
        pred_pragmatic.append(pred_categories["pragmatic"])
        rows.append(
            {
                "document_id": document_id,
                "gold_label": example.gold_label,
                "predicted_label": normalize_label(predicted_label),
                "gold_purist": gold_categories["purist"],
                "predicted_purist": pred_categories["purist"],
                "gold_pragmatic": gold_categories["pragmatic"],
                "predicted_pragmatic": pred_categories["pragmatic"],
                "exact_label_match": normalize_label(predicted_label) == example.gold_label,
            }
        )
    output_dir = Path(args.output_dir)
    report = {
        "documents": len(rows),
        "purist": classification_report(gold_purist, pred_purist),
        "pragmatic": classification_report(gold_pragmatic, pred_pragmatic),
    }
    write_json(output_dir / "gan_frequency_evaluation.json", report)
    write_csv(output_dir / "gan_frequency_predictions_scored.csv", rows)
    print(f"wrote {output_dir / 'gan_frequency_evaluation.json'}")
    print(f"wrote {output_dir / 'gan_frequency_predictions_scored.csv'}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    audit = subparsers.add_parser("audit", help="Audit Gan gold-label category distributions.")
    audit.add_argument("--gan-path", default=str(DEFAULT_GAN_PATH))
    audit.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    audit.set_defaults(func=command_audit)

    evaluate = subparsers.add_parser("evaluate", help="Evaluate normalized-label predictions with Gan category metrics.")
    evaluate.add_argument("--gan-path", default=str(DEFAULT_GAN_PATH))
    evaluate.add_argument("--predictions", required=True, help="JSON object keyed by GAN document_id with normalized label strings.")
    evaluate.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    evaluate.set_defaults(func=command_evaluate)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
