#!/usr/bin/env python3
"""Recovery-phase diagnostic tables for existing extraction runs."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from direct_baselines import load_split_ids, write_json
from evaluate import (
    DEFAULT_DIRECT_RUN_DIR,
    DEFAULT_EVENT_RUN_DIR,
    DEFAULT_MARKUP_ROOT,
    GoldDocument,
    extraction_path,
    load_gold,
    load_json,
    medication_name_tuple,
    medication_tuple,
    normalize_value,
    read_text,
    set_prf,
)
from intake import DEFAULT_EXECT_ROOT, DEFAULT_SPLITS
from normalization import canonical_diagnosis, canonical_seizure_type


WEAK_FIELDS = [
    "medication_name",
    "medication_full",
    "seizure_type",
    "current_seizure_frequency",
    "seizure_frequency_type_linkage",
    "epilepsy_diagnosis",
]

SET_FIELDS = {"medication_name", "medication_full", "seizure_type"}


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def norm_set(items: set[tuple[str, ...]]) -> str:
    rendered = []
    for item in sorted(items):
        if isinstance(item, tuple):
            rendered.append(" | ".join(part for part in item if part))
        else:
            rendered.append(str(item))
    return "; ".join(rendered)


def field_values(data: Any | None, gold: GoldDocument, field: str) -> tuple[Any, Any]:
    fields = data.get("fields", {}) if isinstance(data, dict) else {}

    if field == "medication_name":
        predicted = {medication_name_tuple(item) for item in fields.get("current_anti_seizure_medications", [])}
        expected = {medication_name_tuple(item) for item in gold.medications}
        return predicted, expected

    if field == "medication_full":
        predicted = {medication_tuple(item) for item in fields.get("current_anti_seizure_medications", [])}
        expected = {medication_tuple(item) for item in gold.medications}
        return predicted, expected

    if field == "seizure_type":
        predicted = {
            (canonical_seizure_type(item.get("value")),)
            for item in fields.get("seizure_types", [])
            if canonical_seizure_type(item.get("value"))
        }
        expected = {(item,) for item in set(gold.seizure_types) if item}
        return predicted, expected

    if field == "current_seizure_frequency":
        predicted = normalize_value(fields.get("current_seizure_frequency", {}).get("value"))
        expected = {item["value"] for item in gold.seizure_frequencies if item.get("value")}
        return predicted, expected

    if field == "seizure_frequency_type_linkage":
        predicted = canonical_seizure_type(fields.get("current_seizure_frequency", {}).get("seizure_type"))
        expected = {item["seizure_type"] for item in gold.seizure_frequencies if item.get("seizure_type")}
        return predicted, expected

    if field == "epilepsy_diagnosis":
        predicted = canonical_diagnosis(fields.get("epilepsy_diagnosis", {}).get("value"))
        expected = set(gold.diagnoses)
        return predicted, expected

    raise ValueError(f"unsupported field: {field}")


def scalar_correct(field: str, predicted: str, expected: set[str]) -> bool:
    if field == "epilepsy_diagnosis":
        return any(predicted and (predicted in gold or gold in predicted) for gold in expected)
    return bool(predicted and predicted in expected)


def collapse_epilepsy_or_seizure_label(value: str) -> str:
    text = normalize_value(value)
    if not text:
        return ""
    focal_terms = ["focal", "partial", "temporal lobe", "frontal lobe"]
    generalized_terms = ["generalised", "generalized", "absence", "myoclonic", "tonic clonic"]
    has_focal = any(term in text for term in focal_terms)
    has_generalized = any(term in text for term in generalized_terms)
    if has_focal and has_generalized:
        return "combined_generalized_focal"
    if has_focal:
        return "focal"
    if has_generalized:
        return "generalized"
    if "seizure" in text or "epilepsy" in text or "jme" in text:
        return "unknown"
    return ""


def event_values(path: Path, category: str) -> set[str]:
    data = load_json(path)
    if not isinstance(data, dict):
        return set()
    values = set()
    for event in data.get("events", []):
        if not isinstance(event, dict) or event.get("category") != category:
            continue
        value = event.get("medication_name") if category == "medication" else event.get("value")
        normalized = normalize_value(value)
        if normalized:
            values.add(normalized)
    return values


def e1_contains_gold(args: argparse.Namespace, document_id: str, field: str, gold_item: tuple[str, ...] | str) -> bool:
    if field.startswith("medication"):
        gold_value = gold_item[0] if isinstance(gold_item, tuple) else gold_item
        return gold_value in event_values(Path(args.event_run_dir) / document_id / "e1_events.json", "medication")
    if field in {"seizure_type", "seizure_frequency_type_linkage"}:
        gold_value = gold_item[0] if isinstance(gold_item, tuple) else gold_item
        return gold_value in event_values(Path(args.event_run_dir) / document_id / "e1_events.json", "seizure_type")
    if field == "current_seizure_frequency":
        return bool(event_values(Path(args.event_run_dir) / document_id / "e1_events.json", "seizure_frequency"))
    if field == "epilepsy_diagnosis":
        return bool(event_values(Path(args.event_run_dir) / document_id / "e1_events.json", "diagnosis"))
    return False


def classify_error(
    *,
    system: str,
    field: str,
    error_type: str,
    predicted: Any,
    expected: Any,
    data: Any | None,
    document_id: str,
    args: argparse.Namespace,
) -> str:
    if data is None:
        return "schema_missingness"

    if system == "E2" and error_type == "fn":
        if e1_contains_gold(args, document_id, field, expected):
            return "event_aggregation"
        return "event_extraction"

    if field == "medication_full":
        if isinstance(predicted, tuple):
            pred_names = {predicted[0]}
        else:
            pred_names = {item[0] for item in predicted} if isinstance(predicted, set) else set()
        if isinstance(expected, tuple):
            gold_names = {expected[0]}
        else:
            gold_names = {item[0] for item in expected} if isinstance(expected, set) else set()
        if pred_names & gold_names:
            return "normalizer"
        return "prompt_extraction" if system != "E2" else "event_extraction"

    if field == "medication_name":
        fields = data.get("fields", {}) if isinstance(data, dict) else {}
        if error_type == "fp":
            target = predicted[0] if isinstance(predicted, tuple) else str(predicted)
            for item in fields.get("current_anti_seizure_medications", []):
                if normalize_value(item.get("name")) == target and item.get("temporality") != "current":
                    return "prompt_extraction"
        return "prompt_extraction" if system != "E2" else "event_extraction"

    if field == "seizure_type":
        if isinstance(predicted, tuple):
            predicted_labels = {collapse_epilepsy_or_seizure_label(predicted[0])}
        else:
            predicted_labels = {collapse_epilepsy_or_seizure_label(item[0]) for item in predicted} if isinstance(predicted, set) else set()
        if isinstance(expected, tuple):
            expected_labels = {collapse_epilepsy_or_seizure_label(expected[0])}
        else:
            expected_labels = {collapse_epilepsy_or_seizure_label(item[0]) for item in expected} if isinstance(expected, set) else set()
        if predicted_labels & expected_labels:
            return "normalizer"
        return "prompt_extraction" if system != "E2" else "event_extraction"

    if field == "current_seizure_frequency":
        if isinstance(expected, set) and expected and all("null" in item for item in expected):
            return "gold_loader"
        if predicted:
            return "normalizer"
        return "prompt_extraction" if system != "E2" else "event_extraction"

    if field == "seizure_frequency_type_linkage":
        pred_label = collapse_epilepsy_or_seizure_label(predicted)
        gold_labels = {collapse_epilepsy_or_seizure_label(item) for item in expected}
        if pred_label and pred_label in gold_labels:
            return "normalizer"
        return "prompt_extraction" if system != "E2" else "event_extraction"

    if field == "epilepsy_diagnosis":
        pred_label = collapse_epilepsy_or_seizure_label(predicted)
        gold_labels = {collapse_epilepsy_or_seizure_label(item) for item in expected}
        if pred_label and pred_label in gold_labels:
            return "normalizer"
        return "prompt_extraction" if system != "E2" else "event_extraction"

    return "prompt_extraction"


def source_snippet(source_text: str, value: str, window: int = 220) -> str:
    if not value:
        return source_text[:window].replace("\n", " ")
    index = normalize_value(source_text).find(normalize_value(value))
    if index < 0:
        return source_text[:window].replace("\n", " ")
    start = max(0, index - window // 2)
    end = min(len(source_text), index + len(value) + window // 2)
    return source_text[start:end].replace("\n", " ")


def summarize_e1(args: argparse.Namespace, document_id: str) -> list[dict[str, Any]]:
    path = Path(args.event_run_dir) / document_id / "e1_events.json"
    data = load_json(path)
    if not isinstance(data, dict):
        return []
    return [
        {
            "category": event.get("category"),
            "value": event.get("value"),
            "medication_name": event.get("medication_name"),
            "temporality": event.get("temporality"),
            "status": event.get("status"),
            "evidence": (event.get("evidence") or {}).get("quote") if isinstance(event.get("evidence"), dict) else None,
        }
        for event in data.get("events", [])
        if isinstance(event, dict)
    ]


def summarize_aggregation(args: argparse.Namespace, document_id: str) -> dict[str, Any]:
    path = Path(args.event_run_dir) / document_id / "e2_aggregation_log.json"
    data = load_json(path)
    if not isinstance(data, dict):
        return {}
    return {
        "selected_event_ids": data.get("selected_event_ids"),
        "ignored_event_ids": data.get("ignored_event_ids"),
        "missingness_decisions": data.get("missingness_decisions"),
        "conflict_decisions": data.get("conflict_decisions"),
    }


def command_phase1(args: argparse.Namespace) -> int:
    output_dir = Path(args.output_dir)
    field_confusion_dir = output_dir / "field_confusions"
    review_dir = output_dir / "review_packets"
    gold_by_doc = load_gold(Path(args.markup_root), Path(args.exect_root))

    confusion_rows: list[dict[str, Any]] = []
    error_rows: list[dict[str, Any]] = []
    review_cases: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for split in args.splits_to_analyze:
        document_ids = load_split_ids(Path(args.splits), split, args.limit)
        for system in args.systems:
            for field in WEAK_FIELDS:
                set_tp = set_fp = set_fn = 0
                scalar_correct_count = scalar_total = scalar_missing_pred = scalar_gold_support = 0

                for document_id in document_ids:
                    path = extraction_path(system, document_id, args)
                    data = load_json(path)
                    gold = gold_by_doc.get(document_id, GoldDocument(document_id=document_id))
                    predicted, expected = field_values(data, gold, field)

                    if field in SET_FIELDS:
                        scores = set_prf(predicted, expected)
                        set_tp += int(scores["tp"])
                        set_fp += int(scores["fp"])
                        set_fn += int(scores["fn"])

                        for item in sorted(predicted - expected):
                            source = classify_error(
                                system=system,
                                field=field,
                                error_type="fp",
                                predicted=item,
                                expected=expected,
                                data=data,
                                document_id=document_id,
                                args=args,
                            )
                            error_rows.append(error_record(split, system, document_id, field, "fp", item, expected, source))
                        for item in sorted(expected - predicted):
                            source = classify_error(
                                system=system,
                                field=field,
                                error_type="fn",
                                predicted=predicted,
                                expected=item,
                                data=data,
                                document_id=document_id,
                                args=args,
                            )
                            error_rows.append(error_record(split, system, document_id, field, "fn", predicted, item, source))
                    else:
                        scalar_total += 1
                        scalar_gold_support += 1 if expected else 0
                        scalar_missing_pred += 1 if not predicted else 0
                        correct = scalar_correct(field, predicted, expected)
                        scalar_correct_count += 1 if correct else 0
                        if not correct:
                            source = classify_error(
                                system=system,
                                field=field,
                                error_type="scalar_mismatch",
                                predicted=predicted,
                                expected=expected,
                                data=data,
                                document_id=document_id,
                                args=args,
                            )
                            error_rows.append(
                                error_record(split, system, document_id, field, "scalar_mismatch", predicted, expected, source)
                            )

                if field in SET_FIELDS:
                    precision = set_tp / (set_tp + set_fp) if set_tp + set_fp else 1.0 if set_fn == 0 else 0.0
                    recall = set_tp / (set_tp + set_fn) if set_tp + set_fn else 1.0
                    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
                    confusion_rows.append(
                        {
                            "split": split,
                            "system": system,
                            "field": field,
                            "tp": set_tp,
                            "fp": set_fp,
                            "fn": set_fn,
                            "precision": precision,
                            "recall": recall,
                            "f1": f1,
                            "accuracy": "",
                            "missing_predictions": "",
                            "gold_support_documents": "",
                        }
                    )
                else:
                    confusion_rows.append(
                        {
                            "split": split,
                            "system": system,
                            "field": field,
                            "tp": "",
                            "fp": "",
                            "fn": "",
                            "precision": "",
                            "recall": "",
                            "f1": "",
                            "accuracy": scalar_correct_count / scalar_total if scalar_total else "",
                            "missing_predictions": scalar_missing_pred,
                            "gold_support_documents": scalar_gold_support,
                        }
                    )

    for row in error_rows:
        review_cases[row["field"]].append(row)

    pareto_rows = build_pareto(error_rows)
    write_csv(output_dir / "failure_pareto.csv", pareto_rows)
    write_csv(output_dir / "error_cases.csv", error_rows)
    write_csv(field_confusion_dir / "all_fields.csv", confusion_rows)
    for field in WEAK_FIELDS:
        write_csv(field_confusion_dir / f"{field}.csv", [row for row in confusion_rows if row["field"] == field])

    write_review_packets(review_dir, review_cases, args)
    write_json(
        output_dir / "phase1_manifest.json",
        {
            "phase": "1_failure_localization",
            "systems": args.systems,
            "splits": args.splits_to_analyze,
            "outputs": [
                str(output_dir / "failure_pareto.csv"),
                str(output_dir / "error_cases.csv"),
                str(field_confusion_dir),
                str(review_dir),
            ],
            "error_count": len(error_rows),
            "pareto_rows": len(pareto_rows),
        },
    )

    print(f"wrote {output_dir / 'failure_pareto.csv'}")
    print(f"wrote {field_confusion_dir}")
    print(f"wrote {review_dir}")
    return 0


def error_record(
    split: str,
    system: str,
    document_id: str,
    field: str,
    error_type: str,
    predicted: Any,
    expected: Any,
    failure_source: str,
) -> dict[str, Any]:
    return {
        "split": split,
        "system": system,
        "document_id": document_id,
        "field": field,
        "error_type": error_type,
        "failure_source": failure_source,
        "predicted": norm_set(predicted) if isinstance(predicted, set) else " | ".join(predicted) if isinstance(predicted, tuple) else predicted,
        "gold": norm_set(expected) if isinstance(expected, set) else " | ".join(expected) if isinstance(expected, tuple) else expected,
    }


def build_pareto(error_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts = Counter((row["field"], row["system"], row["failure_source"]) for row in error_rows)
    totals_by_field_system = Counter((row["field"], row["system"]) for row in error_rows)
    rows = []
    cumulative: dict[tuple[str, str], int] = defaultdict(int)
    for (field, system, failure_source), count in counts.most_common():
        key = (field, system)
        cumulative[key] += count
        total = totals_by_field_system[key]
        rows.append(
            {
                "field": field,
                "system": system,
                "failure_source": failure_source,
                "error_count": count,
                "field_system_errors": total,
                "share": count / total if total else 0,
                "cumulative_share": cumulative[key] / total if total else 0,
            }
        )
    return rows


def write_review_packets(review_dir: Path, review_cases: dict[str, list[dict[str, Any]]], args: argparse.Namespace) -> None:
    review_dir.mkdir(parents=True, exist_ok=True)
    gold_by_doc = load_gold(Path(args.markup_root), Path(args.exect_root))
    for field, rows in review_cases.items():
        selected = rows[: args.review_limit]
        packets = []
        for row in selected:
            document_id = row["document_id"]
            source_text = read_text(Path(args.exect_root) / f"{document_id}.txt")
            gold = gold_by_doc.get(document_id, GoldDocument(document_id=document_id))
            s2 = load_json(Path(args.direct_run_dir) / "S2" / document_id / "canonical.json")
            e2 = load_json(Path(args.event_run_dir) / document_id / "e2_canonical.json")
            e3 = load_json(Path(args.event_run_dir) / document_id / "e3_canonical.json")
            packets.append(
                {
                    "error": row,
                    "source_snippet": source_snippet(source_text, str(row.get("gold") or row.get("predicted") or "")),
                    "gold_summary": {
                        "medications": gold.medications,
                        "seizure_frequencies": gold.seizure_frequencies,
                        "seizure_types": sorted(set(gold.seizure_types)),
                        "diagnoses": sorted(set(gold.diagnoses)),
                    },
                    "s2_fields": s2.get("fields") if isinstance(s2, dict) else None,
                    "e1_events": summarize_e1(args, document_id),
                    "e2_fields": e2.get("fields") if isinstance(e2, dict) else None,
                    "e2_aggregation_log": summarize_aggregation(args, document_id),
                    "e3_fields": e3.get("fields") if isinstance(e3, dict) else None,
                }
            )
        write_json(review_dir / f"{field}.json", {"field": field, "sample_size": len(packets), "packets": packets})


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    phase1 = subparsers.add_parser("phase1", help="Build Phase 1 failure-localization outputs.")
    phase1.add_argument("--exect-root", default=str(DEFAULT_EXECT_ROOT))
    phase1.add_argument("--markup-root", default=str(DEFAULT_MARKUP_ROOT))
    phase1.add_argument("--splits", default=str(DEFAULT_SPLITS))
    phase1.add_argument("--splits-to-analyze", nargs="+", default=["validation"], choices=["development", "validation", "test"])
    phase1.add_argument("--limit", type=int)
    phase1.add_argument("--systems", nargs="+", default=["S2", "E2", "E3"], choices=["S2", "E2", "E3"])
    phase1.add_argument("--direct-run-dir", default=str(DEFAULT_DIRECT_RUN_DIR))
    phase1.add_argument("--event-run-dir", default=str(DEFAULT_EVENT_RUN_DIR))
    phase1.add_argument("--output-dir", default="runs/recovery/baseline_failure_localization")
    phase1.add_argument("--review-limit", type=int, default=20)
    phase1.set_defaults(func=command_phase1)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
