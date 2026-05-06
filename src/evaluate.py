#!/usr/bin/env python3
"""Evaluate direct and event-first canonical outputs against ExECTv2 gold labels."""

from __future__ import annotations

import argparse
import csv
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from direct_baselines import load_split_ids, write_json
from intake import DEFAULT_EXECT_ROOT, DEFAULT_SPLITS, load_gold_annotations, read_text
from validate_extraction import DEFAULT_SCHEMA, check_quote_validity, validate_extraction


DEFAULT_MARKUP_ROOT = Path("data/ExECT 2 (2025)/MarkupOutput_200_SyntheticEpilepsyLetters")
DEFAULT_OUTPUT_DIR = Path("runs/evaluation")
DEFAULT_DIRECT_RUN_DIR = Path("runs/direct_baselines")
DEFAULT_EVENT_RUN_DIR = Path("runs/event_first")


@dataclass(frozen=True)
class GoldSpan:
    start: int
    end: int
    label: str
    value: str


@dataclass
class GoldDocument:
    document_id: str
    medications: list[dict[str, str | None]] = field(default_factory=list)
    seizure_frequencies: list[dict[str, str | None]] = field(default_factory=list)
    seizure_types: list[str] = field(default_factory=list)
    investigations: dict[str, str | None] = field(default_factory=lambda: {"eeg": None, "mri": None})
    diagnoses: list[str] = field(default_factory=list)
    spans_by_group: dict[str, list[GoldSpan]] = field(default_factory=dict)


def normalize_value(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip().lower()
    text = text.replace("_", " ").replace("-", " ")
    text = re.sub(r"[^a-z0-9.]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def normalize_frequency(value: Any) -> str:
    mapping = {"1": "once daily", "2": "twice daily", "3": "three times daily", "4": "four times daily"}
    normalized = normalize_value(value)
    if normalized in mapping:
        return mapping[normalized]
    return normalized.replace("bd", "twice daily").replace("od", "once daily").replace("tds", "three times daily")


def document_id_from_filename(filename: str) -> str:
    return Path(filename).stem


def read_csv_rows(path: Path) -> list[list[str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return [[cell.strip() for cell in row] for row in csv.reader(handle)]


def ensure_gold(gold: dict[str, GoldDocument], document_id: str) -> GoldDocument:
    return gold.setdefault(document_id, GoldDocument(document_id=document_id))


def add_span(document: GoldDocument, group: str, start: str, end: str, label: str, value: str) -> None:
    if start.isdigit() and end.isdigit():
        document.spans_by_group.setdefault(group, []).append(GoldSpan(int(start), int(end), label, value))


def load_gold(markup_root: Path = DEFAULT_MARKUP_ROOT, exect_root: Path = DEFAULT_EXECT_ROOT) -> dict[str, GoldDocument]:
    gold: dict[str, GoldDocument] = {}

    for row in read_csv_rows(markup_root / "MarkupPrescriptions.csv"):
        if len(row) < 10:
            continue
        document = ensure_gold(gold, document_id_from_filename(row[0]))
        medication = {
            "name": normalize_value(row[4] if row[4].lower() != "null" else row[5]),
            "dose": normalize_value(row[6]),
            "dose_unit": normalize_value(row[7]),
            "frequency": normalize_frequency(row[8]),
        }
        document.medications.append(medication)
        add_span(document, "medications", row[1], row[2], "Prescription", row[9])

    for row in read_csv_rows(markup_root / "MarkupSeizureFrequency.csv"):
        if len(row) < 11:
            continue
        document = ensure_gold(gold, document_id_from_filename(row[0]))
        exact = normalize_value(row[7])
        lower = normalize_value(row[8])
        upper = normalize_value(row[9])
        period = normalize_value(row[10])
        period_count = normalize_value(row[11]) if len(row) > 11 else ""
        if lower and upper:
            count = f"{lower}-{upper}"
        else:
            count = exact or lower or upper
        frequency = " ".join(part for part in [count, "per", period_count, period] if part and part != "null")
        seizure_type = normalize_value(row[5] if row[5].lower() != "null" else row[4])
        document.seizure_frequencies.append(
            {
                "value": normalize_value(frequency),
                "seizure_type": seizure_type,
                "temporal_scope": normalize_value(" ".join(cell for cell in row[12:] if cell.lower() != "null")),
            }
        )
        if seizure_type:
            document.seizure_types.append(seizure_type)
        add_span(document, "seizure_frequency", row[1], row[2], "SeizureFrequency", row[5])

    for row in read_csv_rows(markup_root / "MarkupInvestigations.csv"):
        if len(row) < 5:
            continue
        document = ensure_gold(gold, document_id_from_filename(row[0]))
        phrase = normalize_value(row[4])
        result = "abnormal" if "abnormal" in phrase else "normal" if "normal" in phrase else None
        if "eeg" in phrase and result:
            document.investigations["eeg"] = result
            add_span(document, "eeg", row[1], row[2], "Investigations", row[5] if len(row) > 5 else row[4])
        if "mri" in phrase and result:
            document.investigations["mri"] = result
            add_span(document, "mri", row[1], row[2], "Investigations", row[5] if len(row) > 5 else row[4])

    for row in read_csv_rows(markup_root / "MarkupDiagnosis.csv"):
        if len(row) < 9:
            continue
        document = ensure_gold(gold, document_id_from_filename(row[0]))
        if normalize_value(row[7]) == "epilepsy" and normalize_value(row[6]) == "affirmed":
            diagnosis = normalize_value(row[5] if row[5].lower() != "null" else row[4])
            if diagnosis:
                document.diagnoses.append(diagnosis)
            add_span(document, "diagnosis", row[1], row[2], "Diagnosis", row[5])

    for document_id in {path.stem for path in exect_root.glob("EA*.ann")}:
        document = ensure_gold(gold, document_id)
        for annotation in load_gold_annotations(document_id, exect_root):
            add_span(document, annotation.label, str(annotation.char_start), str(annotation.char_end), annotation.label, annotation.annotation_text)
    return gold


def load_json(path: Path) -> Any | None:
    if not path.exists():
        return None
    try:
        return json.loads(read_text(path))
    except json.JSONDecodeError:
        return None


def extraction_path(system: str, document_id: str, args: argparse.Namespace) -> Path:
    if system == "S2":
        return Path(args.direct_run_dir) / "S2" / document_id / "canonical.json"
    if system == "S3":
        return Path(args.direct_run_dir) / "S3" / document_id / "canonical.json"
    if system == "E2":
        return Path(args.event_run_dir) / document_id / "e2_canonical.json"
    if system == "E3":
        return Path(args.event_run_dir) / document_id / "e3_canonical.json"
    raise ValueError(f"unsupported system: {system}")


def overlap(a_start: int, a_end: int, b_start: int, b_end: int) -> int:
    return max(0, min(a_end, b_end) - max(a_start, b_start))


def evidence_overlaps_gold(evidence: dict[str, Any], spans: list[GoldSpan]) -> bool:
    start = evidence.get("char_start")
    end = evidence.get("char_end")
    if isinstance(start, int) and isinstance(end, int):
        return any(overlap(start, end, span.start, span.end) > 0 for span in spans)
    quote = normalize_value(evidence.get("quote"))
    return bool(quote and any(quote in normalize_value(span.value) or normalize_value(span.value) in quote for span in spans))


def evidence_support_for_group(field_value: Any, group: str, document_gold: GoldDocument) -> dict[str, Any]:
    evidence = []
    if isinstance(field_value, dict):
        raw = field_value.get("evidence") or []
        evidence = raw if isinstance(raw, list) else []
    spans = document_gold.spans_by_group.get(group, [])
    present = bool(evidence)
    overlap_count = sum(1 for item in evidence if isinstance(item, dict) and evidence_overlaps_gold(item, spans))
    return {
        "present": present,
        "gold_overlap": overlap_count > 0 if present else False,
        "evidence_count": len(evidence),
        "gold_overlap_count": overlap_count,
    }


def set_prf(predicted: set[tuple[str, ...]], gold: set[tuple[str, ...]]) -> dict[str, float | int]:
    tp = len(predicted & gold)
    fp = len(predicted - gold)
    fn = len(gold - predicted)
    precision = tp / (tp + fp) if tp + fp else 1.0 if not gold else 0.0
    recall = tp / (tp + fn) if tp + fn else 1.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"tp": tp, "fp": fp, "fn": fn, "precision": precision, "recall": recall, "f1": f1}


def medication_tuple(item: dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        normalize_value(item.get("name")),
        normalize_value(item.get("dose")),
        normalize_value(item.get("dose_unit")),
        normalize_frequency(item.get("frequency")),
    )


def medication_name_tuple(item: dict[str, Any]) -> tuple[str]:
    return (normalize_value(item.get("name")),)


def score_document(data: Any | None, source_text: str, document_gold: GoldDocument, schema_path: Path) -> dict[str, Any]:
    result: dict[str, Any] = {
        "available": data is not None,
        "schema_valid": False,
        "project_constraints_valid": False,
        "quote_presence": {"present_field_count": 0, "with_evidence_count": 0, "rate": None},
        "quote_validity": {"quote_count": 0, "valid_quote_count": 0, "invalid_quote_count": 0, "rate": None},
        "field_scores": {},
        "evidence_scores": {},
        "semantic_support": {},
        "temporal_scores": {},
        "temporal_support": {},
        "field_correctness": {},
        "cost_latency": {},
        "errors": [],
    }
    if data is None:
        result["errors"].append("missing extraction output")
        return result

    try:
        validate_extraction(data, schema_path, require_present_evidence=True)
        result["schema_valid"] = True
        result["project_constraints_valid"] = True
    except Exception as exc:  # validation errors are reported but scoring continues where possible.
        result["errors"].append(str(exc))

    quote_total, quote_failures = check_quote_validity(data, source_text)
    result["quote_validity"] = {
        "quote_count": quote_total,
        "valid_quote_count": quote_total - len(quote_failures),
        "invalid_quote_count": len(quote_failures),
        "rate": (quote_total - len(quote_failures)) / quote_total if quote_total else 1.0,
        "invalid_quote_paths": quote_failures,
    }

    fields = data.get("fields", {}) if isinstance(data, dict) else {}
    present_fields = []

    def collect_present(value: Any, path: str) -> None:
        if isinstance(value, dict):
            if value.get("missingness") == "present":
                present_fields.append((path, value))
            for key, child in value.items():
                collect_present(child, f"{path}.{key}")
        elif isinstance(value, list):
            for index, child in enumerate(value):
                collect_present(child, f"{path}[{index}]")

    collect_present(fields, "$.fields")
    with_evidence = [item for item in present_fields if item[1].get("evidence")]
    result["quote_presence"] = {
        "present_field_count": len(present_fields),
        "with_evidence_count": len(with_evidence),
        "rate": len(with_evidence) / len(present_fields) if present_fields else 1.0,
    }

    predicted_medications = {medication_tuple(item) for item in fields.get("current_anti_seizure_medications", [])}
    gold_medications = {medication_tuple(item) for item in document_gold.medications}
    predicted_med_names = {medication_name_tuple(item) for item in fields.get("current_anti_seizure_medications", [])}
    gold_med_names = {medication_name_tuple(item) for item in document_gold.medications}
    result["field_scores"]["medication_name"] = set_prf(predicted_med_names, gold_med_names)
    result["field_scores"]["medication_full"] = set_prf(predicted_medications, gold_medications)

    predicted_types = {
        (normalize_value(item.get("value")),)
        for item in fields.get("seizure_types", [])
        if normalize_value(item.get("value"))
    }
    gold_types = {(item,) for item in set(document_gold.seizure_types) if item}
    result["field_scores"]["seizure_type"] = set_prf(predicted_types, gold_types)

    predicted_frequency = normalize_value(fields.get("current_seizure_frequency", {}).get("value"))
    gold_frequencies = {item["value"] for item in document_gold.seizure_frequencies if item.get("value")}
    result["field_scores"]["current_seizure_frequency"] = {
        "correct": bool(predicted_frequency and predicted_frequency in gold_frequencies),
        "predicted": predicted_frequency,
        "gold_values": sorted(gold_frequencies),
    }
    predicted_frequency_type = normalize_value(fields.get("current_seizure_frequency", {}).get("seizure_type"))
    gold_frequency_types = {item["seizure_type"] for item in document_gold.seizure_frequencies if item.get("seizure_type")}
    result["field_scores"]["seizure_frequency_type_linkage"] = {
        "correct": bool(predicted_frequency_type and predicted_frequency_type in gold_frequency_types),
        "predicted": predicted_frequency_type,
        "gold_values": sorted(gold_frequency_types),
    }

    for field_name in ["eeg", "mri"]:
        predicted = normalize_value(fields.get(field_name, {}).get("result"))
        gold = document_gold.investigations.get(field_name)
        result["field_scores"][field_name] = {
            "correct": (predicted == gold) if gold else predicted in {"", "not stated", "none"},
            "predicted": predicted,
            "gold": gold,
        }

    predicted_diagnosis = normalize_value(fields.get("epilepsy_diagnosis", {}).get("value"))
    result["field_scores"]["epilepsy_diagnosis"] = {
        "correct": any(predicted_diagnosis and (predicted_diagnosis in gold or gold in predicted_diagnosis) for gold in document_gold.diagnoses),
        "predicted": predicted_diagnosis,
        "gold_values": sorted(set(document_gold.diagnoses)),
    }

    group_map = {
        "current_seizure_frequency": "seizure_frequency",
        "eeg": "eeg",
        "mri": "mri",
        "epilepsy_diagnosis": "diagnosis",
    }
    for field_name, group in group_map.items():
        result["evidence_scores"][field_name] = evidence_support_for_group(fields.get(field_name, {}), group, document_gold)
        result["semantic_support"][field_name] = result["evidence_scores"][field_name]
    medication_support = [
        evidence_support_for_group(item, "medications", document_gold)
        for item in fields.get("current_anti_seizure_medications", [])
    ]
    result["evidence_scores"]["current_anti_seizure_medications"] = {
        "field_count": len(medication_support),
        "supported_count": sum(1 for item in medication_support if item["gold_overlap"]),
    }
    result["semantic_support"]["current_anti_seizure_medications"] = result["evidence_scores"][
        "current_anti_seizure_medications"
    ]

    temporal_checks = []
    for item in fields.get("current_anti_seizure_medications", []):
        temporal_checks.append(item.get("temporality") == "current" and item.get("status") == "current")
    for field_name in ["current_seizure_frequency", "epilepsy_diagnosis"]:
        field_value = fields.get(field_name, {})
        if field_value.get("missingness") == "present":
            temporal_checks.append(field_value.get("temporality") in {"current", "uncertain"})
    for field_name in ["eeg", "mri"]:
        field_value = fields.get(field_name, {})
        if field_value.get("missingness") == "present":
            temporal_checks.append(field_value.get("status") == "completed")
    result["temporal_scores"] = {
        "checked_count": len(temporal_checks),
        "correct_count": sum(1 for item in temporal_checks if item),
        "accuracy": sum(1 for item in temporal_checks if item) / len(temporal_checks) if temporal_checks else 1.0,
    }
    result["temporal_support"] = result["temporal_scores"]
    result["field_correctness"] = result["field_scores"]

    metadata = data.get("metadata", {}) if isinstance(data, dict) else {}
    result["cost_latency"] = {
        "latency_ms": metadata.get("latency_ms"),
        "input_tokens": metadata.get("input_tokens"),
        "output_tokens": metadata.get("output_tokens"),
        "estimated_cost_usd": metadata.get("estimated_cost_usd"),
    }
    return result


def flatten_summary(system: str, document_scores: list[dict[str, Any]]) -> dict[str, Any]:
    available = [score for score in document_scores if score["available"]]
    if not available:
        return {
            "system": system,
            "documents_expected": len(document_scores),
            "documents_available": 0,
            "schema_valid_rate": 0.0,
            "quote_presence_rate": None,
            "quote_validity_rate": None,
            "temporal_accuracy": None,
            "medication_name_f1": None,
            "medication_full_f1": None,
            "seizure_type_f1": None,
            "current_seizure_frequency_accuracy": None,
            "seizure_frequency_type_linkage_accuracy": None,
            "eeg_accuracy": None,
            "mri_accuracy": None,
            "epilepsy_diagnosis_accuracy": None,
            "mean_latency_ms": None,
            "mean_input_tokens": None,
            "mean_output_tokens": None,
            "mean_estimated_cost_usd": None,
        }
    schema_valid = sum(1 for score in available if score["schema_valid"])
    quote_count = sum(score["quote_validity"]["quote_count"] for score in available)
    valid_quote_count = sum(score["quote_validity"]["valid_quote_count"] for score in available)
    present_count = sum(score["quote_presence"]["present_field_count"] for score in available)
    evidence_count = sum(score["quote_presence"]["with_evidence_count"] for score in available)
    temporal_checked = sum(score["temporal_scores"]["checked_count"] for score in available)
    temporal_correct = sum(score["temporal_scores"]["correct_count"] for score in available)

    totals: dict[str, dict[str, int]] = {}
    for metric in ["medication_name", "medication_full", "seizure_type"]:
        totals[metric] = {"tp": 0, "fp": 0, "fn": 0}
        for score in available:
            metric_score = score["field_scores"].get(metric, {})
            for key in totals[metric]:
                totals[metric][key] += int(metric_score.get(key, 0))

    prf_metrics = {}
    for metric, counts in totals.items():
        tp, fp, fn = counts["tp"], counts["fp"], counts["fn"]
        precision = tp / (tp + fp) if tp + fp else 1.0 if fn == 0 else 0.0
        recall = tp / (tp + fn) if tp + fn else 1.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        prf_metrics[metric] = {"tp": tp, "fp": fp, "fn": fn, "precision": precision, "recall": recall, "f1": f1}

    def accuracy(metric: str) -> float | None:
        values = [score["field_scores"][metric]["correct"] for score in available if metric in score["field_scores"]]
        return sum(1 for item in values if item) / len(values) if values else None

    latencies = [
        score["cost_latency"]["latency_ms"]
        for score in available
        if isinstance(score["cost_latency"].get("latency_ms"), (int, float))
    ]
    input_tokens = [
        score["cost_latency"]["input_tokens"]
        for score in available
        if isinstance(score["cost_latency"].get("input_tokens"), (int, float))
    ]
    output_tokens = [
        score["cost_latency"]["output_tokens"]
        for score in available
        if isinstance(score["cost_latency"].get("output_tokens"), (int, float))
    ]
    costs = [
        score["cost_latency"]["estimated_cost_usd"]
        for score in available
        if isinstance(score["cost_latency"].get("estimated_cost_usd"), (int, float))
    ]
    return {
        "system": system,
        "documents_expected": len(document_scores),
        "documents_available": len(available),
        "schema_valid_rate": schema_valid / len(available) if available else 0.0,
        "quote_presence_rate": evidence_count / present_count if present_count else 1.0,
        "quote_validity_rate": valid_quote_count / quote_count if quote_count else 1.0,
        "temporal_accuracy": temporal_correct / temporal_checked if temporal_checked else 1.0,
        "medication_name_f1": prf_metrics["medication_name"]["f1"],
        "medication_full_f1": prf_metrics["medication_full"]["f1"],
        "seizure_type_f1": prf_metrics["seizure_type"]["f1"],
        "current_seizure_frequency_accuracy": accuracy("current_seizure_frequency"),
        "seizure_frequency_type_linkage_accuracy": accuracy("seizure_frequency_type_linkage"),
        "eeg_accuracy": accuracy("eeg"),
        "mri_accuracy": accuracy("mri"),
        "epilepsy_diagnosis_accuracy": accuracy("epilepsy_diagnosis"),
        "mean_latency_ms": sum(latencies) / len(latencies) if latencies else None,
        "mean_input_tokens": sum(input_tokens) / len(input_tokens) if input_tokens else None,
        "mean_output_tokens": sum(output_tokens) / len(output_tokens) if output_tokens else None,
        "mean_estimated_cost_usd": sum(costs) / len(costs) if costs else None,
    }


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


def format_metric(value: Any) -> str:
    return f"{value:.3f}" if isinstance(value, (int, float)) else "n/a"


def command_run(args: argparse.Namespace) -> int:
    systems = args.systems
    document_ids = load_split_ids(Path(args.splits), args.split, args.limit)
    gold = load_gold(Path(args.markup_root), Path(args.exect_root))
    output_dir = Path(args.output_dir)
    all_scores: dict[str, list[dict[str, Any]]] = {system: [] for system in systems}

    for system in systems:
        for document_id in document_ids:
            data = load_json(extraction_path(system, document_id, args))
            source_text = read_text(Path(args.exect_root) / f"{document_id}.txt")
            document_gold = gold.get(document_id, GoldDocument(document_id=document_id))
            score = score_document(data, source_text, document_gold, Path(args.schema))
            score["document_id"] = document_id
            score["system"] = system
            all_scores[system].append(score)

    summaries = [flatten_summary(system, all_scores[system]) for system in systems]
    write_json(output_dir / "evaluation_summary.json", {"split": args.split, "systems": systems, "summaries": summaries})
    write_json(output_dir / "document_scores.json", all_scores)
    write_csv(output_dir / "comparison_table.csv", summaries)

    for row in summaries:
        print(
            f"{row['system']}: docs={row['documents_available']}/{row['documents_expected']} "
            f"schema={format_metric(row['schema_valid_rate'])} "
            f"quote_valid={format_metric(row['quote_validity_rate'])} "
            f"med_full_f1={format_metric(row['medication_full_f1'])}"
        )
    print(f"wrote {output_dir / 'evaluation_summary.json'}")
    print(f"wrote {output_dir / 'comparison_table.csv'}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    run = subparsers.add_parser("run", help="Score existing canonical run outputs.")
    run.add_argument("--exect-root", default=str(DEFAULT_EXECT_ROOT))
    run.add_argument("--markup-root", default=str(DEFAULT_MARKUP_ROOT))
    run.add_argument("--splits", default=str(DEFAULT_SPLITS))
    run.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    run.add_argument("--split", default="validation", choices=["development", "validation", "test"])
    run.add_argument("--limit", type=int)
    run.add_argument("--systems", nargs="+", default=["S2", "E2", "E3"], choices=["S2", "S3", "E2", "E3"])
    run.add_argument("--direct-run-dir", default=str(DEFAULT_DIRECT_RUN_DIR))
    run.add_argument("--event-run-dir", default=str(DEFAULT_EVENT_RUN_DIR))
    run.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    run.set_defaults(func=command_run)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
