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

from direct_baselines import parse_json_response
from intake import read_text
from model_providers import ModelRequest, adapter_for, write_response_log
from model_registry import DEFAULT_REGISTRY, load_model_specs


DEFAULT_GAN_PATH = Path("data/Gan (2026)/synthetic_data_subset_1500.json")
DEFAULT_OUTPUT_DIR = Path("runs/gan_frequency")
DEFAULT_REGISTRY_PATH = DEFAULT_REGISTRY
UNKNOWN_X = 1000.0
MULTIPLE_VALUE = 2.0
GAN_LABEL_FALLBACK = "unknown"
GAN_HARNESSES = ["Gan_direct_label", "Gan_cot_label", "Gan_evidence_label", "Gan_two_pass", "Gan_fs_hard"]


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


def gan_direct_label_prompt(example: GanExample) -> str:
    return f"""## Task
Extract the current clinically relevant seizure frequency from this epilepsy clinic letter.

Return JSON:
{{"seizure_frequency_number": "<normalized Gan label>", "quote": "<verbatim supporting evidence>"}}

Use exactly one normalized label using these forms:
- "<n> per <period>"
- "<n1> to <n2> per <period>"
- "<n> cluster per <period>, <m> per cluster"
- "seizure free for <n> month"
- "seizure free for multiple month"
- "unknown"
- "no seizure frequency reference"

Use "unknown" when seizures are mentioned but no specific frequency can be determined.
Use "no seizure frequency reference" when the letter does not mention seizure frequency.

Examples:
- "Two events over the last five months" -> "2 per 5 month"
- "3-4 focal aware seizures per month" -> "3 to 4 per month"
- "clusters twice monthly, six seizures per cluster" -> "2 cluster per month, 6 per cluster"
- "seizure-free for 12 months" -> "seizure free for 12 month"
- "seizures are sporadic but frequency unclear" -> "unknown"

## Clinical letter
{example.text}
"""


def gan_cot_label_prompt(example: GanExample) -> str:
    return f"""## Task
Extract the current clinically relevant seizure frequency from this epilepsy clinic letter.

Think through the relevant evidence before choosing the final normalized label, but return only
the JSON object below.

Return JSON:
{{"seizure_frequency_number": "<normalized Gan label>", "quote": "<verbatim supporting evidence>"}}

Allowed labels:
- "<n> per <period>"
- "<n1> to <n2> per <period>"
- "<n> cluster per <period>, <m> per cluster"
- "seizure free for <n> month"
- "seizure free for multiple month"
- "unknown"
- "no seizure frequency reference"

Use "unknown" when seizures are mentioned but no specific frequency can be determined.
Use "no seizure frequency reference" when the letter does not mention seizure frequency.

Prioritize current clinically relevant frequency over historical frequency unless the letter only
contains seizure-free duration or frequency since the last visit.

## Clinical letter
{example.text}
"""


def gan_evidence_label_prompt(example: GanExample) -> str:
    return f"""## Task
Extract the current clinically relevant seizure frequency from this epilepsy clinic letter.

First identify the shortest exact quote that supports the answer. Then normalize that quote to
one Gan-style label.

Return JSON:
{{"seizure_frequency_number": "<normalized Gan label>", "quote": "<verbatim supporting evidence>"}}

Allowed labels:
- "<n> per <period>"
- "<n1> to <n2> per <period>"
- "<n> cluster per <period>, <m> per cluster"
- "seizure free for <n> month"
- "seizure free for multiple month"
- "unknown"
- "no seizure frequency reference"

If there is no frequency statement, set the label to "no seizure frequency reference" and quote
the most relevant epilepsy context. If frequency is discussed but cannot be quantified, set the
label to "unknown" and quote the uncertainty.

## Clinical letter
{example.text}
"""


def gan_fs_hard_prompt(example: GanExample) -> str:
    return f"""## Task
Extract the current clinically relevant seizure frequency from this epilepsy clinic letter.

Return JSON:
{{"seizure_frequency_number": "<normalized Gan label>", "quote": "<verbatim supporting evidence>"}}

Use exactly one normalized Gan label.

Hard examples:
- "No attacks since the last appointment three months ago" -> "seizure free for multiple month"
- "No seizures for 14 months" -> "seizure free for 14 month"
- "Sporadic jerks this year, exact count unclear" -> "unknown"
- "The letter discusses epilepsy but gives no frequency" -> "no seizure frequency reference"
- "Cluster days twice this month; typically six seizures in 24 h" -> "2 cluster per month, 6 per cluster"
- "Two events over the last five months" -> "2 per 5 month"
- "3-4 focal aware seizures per month" -> "3 to 4 per month"

Use "unknown" when seizures are mentioned but no specific frequency can be determined.
Use "no seizure frequency reference" when the letter does not mention seizure frequency.

## Clinical letter
{example.text}
"""


def gan_two_pass_evidence_prompt(example: GanExample) -> str:
    return f"""## Task
Find the exact text evidence needed to determine seizure frequency.

Quote every sentence or clause that mentions seizure rate, seizure-free status, clusters,
unknown frequency, absence of frequency information, or timing since the last clinic visit.

Return JSON:
{{"evidence": ["<verbatim quote>", "..."]}}

## Clinical letter
{example.text}
"""


def gan_two_pass_normalize_prompt(example: GanExample, evidence: list[str]) -> str:
    evidence_text = "\n".join(f"- {item}" for item in evidence) if evidence else "- No evidence quoted"
    return f"""## Task
Normalize the seizure-frequency evidence into exactly one Gan-style label.

Return JSON:
{{"seizure_frequency_number": "<normalized Gan label>", "quote": "<verbatim supporting evidence>"}}

Allowed labels:
- "<n> per <period>"
- "<n1> to <n2> per <period>"
- "<n> cluster per <period>, <m> per cluster"
- "seizure free for <n> month"
- "seizure free for multiple month"
- "unknown"
- "no seizure frequency reference"

Use "unknown" when seizures are mentioned but no specific frequency can be determined.
Use "no seizure frequency reference" when the quoted evidence shows no seizure-frequency reference.

## Evidence
{evidence_text}
"""


def gan_prompt_for_harness(example: GanExample, harness: str) -> str:
    if harness == "Gan_direct_label":
        return gan_direct_label_prompt(example)
    if harness == "Gan_cot_label":
        return gan_cot_label_prompt(example)
    if harness == "Gan_evidence_label":
        return gan_evidence_label_prompt(example)
    if harness == "Gan_fs_hard":
        return gan_fs_hard_prompt(example)
    raise ValueError(f"unsupported single-pass Gan harness: {harness}")


def gan_prediction_schema() -> dict[str, Any]:
    return {
        "name": "gan_seizure_frequency_prediction",
        "strict": True,
        "schema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "seizure_frequency_number": {"type": "string"},
                "quote": {"type": "string"},
            },
            "required": ["seizure_frequency_number", "quote"],
        },
    }


def gan_evidence_schema() -> dict[str, Any]:
    return {
        "name": "gan_seizure_frequency_evidence",
        "strict": True,
        "schema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "evidence": {
                    "type": "array",
                    "items": {"type": "string"},
                },
            },
            "required": ["evidence"],
        },
    }


def extract_predicted_label(text: str) -> tuple[str, str | None, str]:
    parsed = parse_json_response(text)
    if isinstance(parsed.data, dict):
        raw_label = (
            parsed.data.get("seizure_frequency_number")
            or parsed.data.get("current_seizure_frequency")
            or parsed.data.get("label")
            or parsed.data.get("frequency")
        )
        quote = parsed.data.get("quote") or parsed.data.get("evidence")
        if raw_label:
            return normalize_label(raw_label), str(quote or ""), parsed.error or ""
        return GAN_LABEL_FALLBACK, str(quote or ""), parsed.error or "JSON response missing seizure_frequency_number"
    stripped = text.strip()
    if stripped:
        first_line = stripped.splitlines()[0].strip().strip('"')
        if first_line:
            return normalize_label(first_line), "", parsed.error or ""
    return GAN_LABEL_FALLBACK, "", parsed.error or "no parseable label"


def extract_evidence_quotes(text: str) -> tuple[list[str], str]:
    parsed = parse_json_response(text)
    if isinstance(parsed.data, dict):
        raw_evidence = parsed.data.get("evidence") or parsed.data.get("quotes") or []
        if isinstance(raw_evidence, list):
            return [str(item) for item in raw_evidence if str(item).strip()], parsed.error or ""
        if isinstance(raw_evidence, str) and raw_evidence.strip():
            return [raw_evidence], parsed.error or ""
        return [], parsed.error or "JSON response missing evidence"
    return [], parsed.error or "no parseable evidence JSON"


def call_model(
    adapter: Any,
    spec: Any,
    example: GanExample,
    harness: str,
    prompt: str,
    schema: dict[str, Any],
    args: argparse.Namespace,
    doc_dir: Path,
    pass_name: str,
) -> Any:
    pass_dir = doc_dir / pass_name
    pass_dir.mkdir(parents=True, exist_ok=True)
    (pass_dir / "prompt.txt").write_text(prompt, encoding="utf-8")
    request = ModelRequest(
        prompt=prompt,
        model=spec,
        harness_id=harness,
        temperature=args.temperature,
        max_output_tokens=args.max_output_tokens,
        schema_mode="json_schema",
        response_json_schema=schema,
        metadata={
            "document_id": example.document_id,
            "source_row_index": example.source_row_index,
            "benchmark": "Gan 2026 seizure frequency",
            "pass": pass_name,
        },
    )
    response = adapter.call(request)
    (pass_dir / "raw_response.txt").write_text(response.text, encoding="utf-8")
    write_response_log(response, pass_dir / "provider_response.json")
    return response


def response_total_cost(response: Any) -> float | None:
    value = response.estimated_cost.get("total") if getattr(response, "estimated_cost", None) else None
    return value if isinstance(value, (int, float)) else None


def sum_optional_numbers(values: list[Any]) -> float | int | None:
    numeric = [value for value in values if isinstance(value, (int, float))]
    return sum(numeric) if numeric else None


def command_predict(args: argparse.Namespace) -> int:
    examples = load_gan_examples(Path(args.gan_path))
    if args.document_ids:
        wanted = set(args.document_ids)
        examples = [example for example in examples if example.document_id in wanted]
    if args.limit is not None:
        examples = examples[: args.limit]
    if not examples:
        raise ValueError("no Gan examples selected")

    specs = load_model_specs(Path(args.registry))
    if args.model not in specs:
        raise ValueError(f"model {args.model!r} not found in {args.registry}")
    spec = specs[args.model]
    provider = "stub" if args.stub_calls else spec.provider
    adapter = adapter_for(provider)
    output_dir = Path(args.output_dir)
    calls_dir = output_dir / "calls" / args.model / args.harness
    predictions: dict[str, str] = {}
    rows: list[dict[str, Any]] = []

    for example in examples:
        doc_dir = calls_dir / example.document_id
        if args.harness == "Gan_two_pass":
            evidence_response = call_model(
                adapter,
                spec,
                example,
                args.harness,
                gan_two_pass_evidence_prompt(example),
                gan_evidence_schema(),
                args,
                doc_dir,
                "pass1_evidence",
            )
            evidence_quotes, evidence_error = extract_evidence_quotes(evidence_response.text)
            response = call_model(
                adapter,
                spec,
                example,
                args.harness,
                gan_two_pass_normalize_prompt(example, evidence_quotes),
                gan_prediction_schema(),
                args,
                doc_dir,
                "pass2_normalize",
            )
            raw_response_path = doc_dir / "pass2_normalize" / "raw_response.txt"
            extra_parse_error = evidence_error
            calls_per_doc = 2
            pass_responses = [evidence_response, response]
        else:
            response = call_model(
                adapter,
                spec,
                example,
                args.harness,
                gan_prompt_for_harness(example, args.harness),
                gan_prediction_schema(),
                args,
                doc_dir,
                "pass1_label",
            )
            evidence_quotes = []
            raw_response_path = doc_dir / "pass1_label" / "raw_response.txt"
            extra_parse_error = ""
            calls_per_doc = 1
            pass_responses = [response]
        predicted_label, quote, parse_error = extract_predicted_label(response.text)
        parse_error = "; ".join(item for item in [extra_parse_error, parse_error] if item)
        if response.error and predicted_label == GAN_LABEL_FALLBACK:
            parse_error = response.error
        provider_error = "; ".join(item for item in (pass_response.error for pass_response in pass_responses) if item)
        latency_ms = sum_optional_numbers([pass_response.latency_ms for pass_response in pass_responses])
        input_tokens = sum_optional_numbers([pass_response.token_usage.input_tokens for pass_response in pass_responses])
        output_tokens = sum_optional_numbers([pass_response.token_usage.output_tokens for pass_response in pass_responses])
        estimated_cost_usd = sum_optional_numbers([response_total_cost(pass_response) for pass_response in pass_responses])
        predictions[example.document_id] = predicted_label
        rows.append(
            {
                "document_id": example.document_id,
                "source_row_index": example.source_row_index,
                "model": args.model,
                "provider": provider,
                "harness": args.harness,
                "predicted_label": predicted_label,
                "gold_label": example.gold_label,
                "quote": quote or "",
                "evidence_quotes": " || ".join(evidence_quotes),
                "parse_error": parse_error or "",
                "provider_error": provider_error,
                "calls_per_doc": calls_per_doc,
                "latency_ms": latency_ms,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "estimated_cost_usd": estimated_cost_usd,
                "raw_response_path": str(raw_response_path),
            }
        )

    write_json(output_dir / "predictions.json", predictions)
    write_csv(output_dir / "call_report.csv", rows)
    print(f"wrote {output_dir / 'predictions.json'}")
    print(f"wrote {output_dir / 'call_report.csv'}")
    if args.evaluate:
        eval_args = argparse.Namespace(
            gan_path=args.gan_path,
            predictions=str(output_dir / "predictions.json"),
            output_dir=str(output_dir),
        )
        command_evaluate(eval_args)
    return 0


def safe_condition_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("_")


def read_csv_rows_as_dicts(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def command_sweep(args: argparse.Namespace) -> int:
    output_dir = Path(args.output_dir)
    rows: list[dict[str, Any]] = []
    for model in args.models:
        for harness in args.harnesses:
            condition = f"{safe_condition_name(model)}_{safe_condition_name(harness)}"
            condition_dir = output_dir / condition
            predict_args = argparse.Namespace(
                gan_path=args.gan_path,
                registry=args.registry,
                model=model,
                harness=harness,
                output_dir=str(condition_dir),
                limit=args.limit,
                document_ids=args.document_ids,
                temperature=args.temperature,
                max_output_tokens=args.max_output_tokens,
                stub_calls=args.stub_calls,
                evaluate=True,
            )
            command_predict(predict_args)
            evaluation = json.loads(read_text(condition_dir / "gan_frequency_evaluation.json"))
            scored = read_csv_rows_as_dicts(condition_dir / "gan_frequency_predictions_scored.csv")
            call_report = read_csv_rows_as_dicts(condition_dir / "call_report.csv")
            exact_matches = sum(1 for row in scored if str(row.get("exact_label_match")).lower() == "true")
            total_cost = 0.0
            cost_count = 0
            for row in call_report:
                try:
                    total_cost += float(row.get("estimated_cost_usd") or 0.0)
                    cost_count += 1
                except ValueError:
                    continue
            documents = int(evaluation.get("documents") or 0)
            rows.append(
                {
                    "condition": condition,
                    "model": model,
                    "harness": harness,
                    "documents": documents,
                    "pragmatic_micro_f1": evaluation["pragmatic"]["micro_f1"],
                    "purist_micro_f1": evaluation["purist"]["micro_f1"],
                    "exact_label_accuracy": exact_matches / len(scored) if scored else None,
                    "estimated_total_cost_usd": total_cost if cost_count else None,
                    "estimated_cost_per_doc": total_cost / documents if cost_count and documents else None,
                    "output_dir": str(condition_dir),
                }
            )
    rows.sort(key=lambda row: (row["pragmatic_micro_f1"], row["purist_micro_f1"]), reverse=True)
    write_csv(output_dir / "comparison_table.csv", rows)
    best = rows[0] if rows else None
    decision_lines = [
        "# Stage G2 Promotion Decision",
        "",
        f"Stub calls: {args.stub_calls}",
        f"Documents per condition: {args.limit if args.limit is not None else 'all selected'}",
        "",
    ]
    if best:
        promoted = best["pragmatic_micro_f1"] >= 0.75
        decision_lines.extend(
            [
                f"Best condition: `{best['condition']}`",
                f"Pragmatic micro-F1: {best['pragmatic_micro_f1']:.3f}",
                f"Purist micro-F1: {best['purist_micro_f1']:.3f}",
                f"Promotion rule met: {'yes' if promoted else 'no'}",
                "",
                "Next action:",
                "- Promote this condition to Stage G3 hard-case prompt development." if promoted else "- Do not promote yet; inspect errors before expanding the run.",
            ]
        )
    else:
        decision_lines.append("No conditions were run.")
    (output_dir / "promotion_decision.md").write_text("\n".join(decision_lines) + "\n", encoding="utf-8")
    print(f"wrote {output_dir / 'comparison_table.csv'}")
    print(f"wrote {output_dir / 'promotion_decision.md'}")
    return 0


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

    predict = subparsers.add_parser("predict", help="Run the Stage G1 Gan frequency-only prediction harness.")
    predict.add_argument("--gan-path", default=str(DEFAULT_GAN_PATH))
    predict.add_argument("--registry", default=str(DEFAULT_REGISTRY_PATH))
    predict.add_argument("--model", default="gpt_4_1_mini_baseline")
    predict.add_argument("--harness", default="Gan_direct_label", choices=GAN_HARNESSES)
    predict.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR / "stage_g1" / "gpt_4_1_mini_baseline_direct"))
    predict.add_argument("--limit", type=int)
    predict.add_argument("--document-ids", nargs="*")
    predict.add_argument("--temperature", type=float, default=0.0)
    predict.add_argument("--max-output-tokens", type=int, default=512)
    predict.add_argument("--stub-calls", action="store_true", help="Use the stub adapter instead of calling the configured provider.")
    predict.add_argument("--evaluate", action="store_true", help="Immediately score predictions with Gan category metrics.")
    predict.set_defaults(func=command_predict)

    sweep = subparsers.add_parser("sweep", help="Run a Stage G2 Gan model x harness sweep.")
    sweep.add_argument("--gan-path", default=str(DEFAULT_GAN_PATH))
    sweep.add_argument("--registry", default=str(DEFAULT_REGISTRY_PATH))
    sweep.add_argument("--models", nargs="+", default=["gpt_4_1_mini_baseline"])
    sweep.add_argument("--harnesses", nargs="+", default=GAN_HARNESSES, choices=GAN_HARNESSES)
    sweep.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR / "stage_g2"))
    sweep.add_argument("--limit", type=int, default=150)
    sweep.add_argument("--document-ids", nargs="*")
    sweep.add_argument("--temperature", type=float, default=0.0)
    sweep.add_argument("--max-output-tokens", type=int, default=512)
    sweep.add_argument("--stub-calls", action="store_true", help="Use the stub adapter instead of calling configured providers.")
    sweep.set_defaults(func=command_sweep)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
