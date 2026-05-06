#!/usr/bin/env python3
"""Generate and evaluate robustness perturbations for extraction pipelines."""

from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable

from direct_baselines import load_split_ids, write_json
from evaluate import (
    DEFAULT_DIRECT_RUN_DIR,
    DEFAULT_EVENT_RUN_DIR,
    DEFAULT_MARKUP_ROOT,
    flatten_summary,
    load_gold,
    load_json,
    score_document,
)
from intake import DEFAULT_EXECT_ROOT, DEFAULT_SPLITS, document_ids, read_text
from validate_extraction import DEFAULT_SCHEMA, check_quote_validity, validate_extraction


DEFAULT_OUTPUT_DIR = Path("runs/robustness")
DEFAULT_GAN_PATH = Path("data/Gan (2026)/synthetic_data_subset_1500.json")
LABEL_PRESERVING = "label_preserving"
LABEL_CHANGING = "label_changing"
GAN_FREQUENCY = "gan_frequency"


@dataclass(frozen=True)
class Perturbation:
    id: str
    label_effect: str
    source_dataset: str
    description: str
    apply: Callable[[str, str], str]


@dataclass(frozen=True)
class PerturbedRecord:
    document_id: str
    source_document_id: str
    source_dataset: str
    perturbation_id: str
    label_effect: str
    text_path: str
    description: str
    expected: dict[str, Any] | None = None


def sanitize_id(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_]+", "_", value).strip("_")


def split_sections(text: str) -> list[str]:
    sections = re.split(r"\n\s*\n+", text.strip())
    return [section.strip() for section in sections if section.strip()]


def reorder_sections(text: str, _: str) -> str:
    sections = split_sections(text)
    if len(sections) < 4:
        return text
    header, body = sections[0], sections[1:]
    return "\n\n".join([header, *reversed(body)])


def remove_headings(text: str, _: str) -> str:
    lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.endswith(":") and len(stripped.split()) <= 5:
            continue
        lines.append(line)
    return "\n".join(lines)


def bullets_to_prose(text: str, _: str) -> str:
    lines = []
    buffer: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith(("-", "*", "•")):
            buffer.append(stripped.lstrip("-*• ").rstrip("."))
            continue
        if buffer:
            lines.append(" ".join(item + "." for item in buffer))
            buffer = []
        lines.append(line)
    if buffer:
        lines.append(" ".join(item + "." for item in buffer))
    return "\n".join(lines)


def add_historical_medication(text: str, _: str) -> str:
    trap = (
        "\n\nHistorical medication note: In childhood the patient previously tried "
        "carbamazepine 200 mg twice daily, but this was stopped years ago and is not current."
    )
    return text.rstrip() + trap + "\n"


def add_planned_medication_change(text: str, _: str) -> str:
    trap = (
        "\n\nPlanned change: If seizures worsen in future, we may consider adding "
        "levetiracetam 250 mg twice daily. No change is being made today."
    )
    return text.rstrip() + trap + "\n"


def add_family_history_trap(text: str, _: str) -> str:
    trap = (
        "\n\nFamily history: The patient's brother had weekly focal seizures as a child, "
        "but the patient has not had those events."
    )
    return text.rstrip() + trap + "\n"


def add_negated_investigation(text: str, _: str) -> str:
    trap = "\n\nInvestigation note: There is no report of an abnormal MRI in this letter.\n"
    return text.rstrip() + trap


def add_current_seizure_free_contrast(text: str, _: str) -> str:
    replacement = (
        "\n\nUpdated seizure frequency: Previously seizures were weekly, but the current "
        "seizure frequency is seizure-free for the last six months."
    )
    return text.rstrip() + replacement + "\n"


def add_requested_mri_contrast(text: str, _: str) -> str:
    replacement = (
        "\n\nUpdated investigation plan: MRI brain has been requested and is pending; "
        "there is no completed MRI result available today."
    )
    return text.rstrip() + replacement + "\n"


EXECT_PERTURBATIONS = [
    Perturbation(
        "reordered_sections",
        LABEL_PRESERVING,
        "exectv2",
        "Move section order while preserving source facts.",
        reorder_sections,
    ),
    Perturbation(
        "removed_headings",
        LABEL_PRESERVING,
        "exectv2",
        "Remove short heading lines such as Diagnosis or Current Medication.",
        remove_headings,
    ),
    Perturbation(
        "bullets_to_prose",
        LABEL_PRESERVING,
        "exectv2",
        "Convert bullet-list formatting into prose-like sentences.",
        bullets_to_prose,
    ),
    Perturbation(
        "historical_medication_trap",
        LABEL_PRESERVING,
        "exectv2",
        "Add a clearly historical non-current medication mention.",
        add_historical_medication,
    ),
    Perturbation(
        "planned_medication_trap",
        LABEL_PRESERVING,
        "exectv2",
        "Add a future planned medication mention that should not alter current medication labels.",
        add_planned_medication_change,
    ),
    Perturbation(
        "family_history_trap",
        LABEL_PRESERVING,
        "exectv2",
        "Add a family-history seizure-frequency mention that should not alter patient fields.",
        add_family_history_trap,
    ),
    Perturbation(
        "negated_investigation_trap",
        LABEL_PRESERVING,
        "exectv2",
        "Add a negated abnormal MRI statement.",
        add_negated_investigation,
    ),
    Perturbation(
        "current_seizure_free_contrast",
        LABEL_CHANGING,
        "exectv2",
        "Add a current seizure-free contrast after a historical weekly frequency.",
        add_current_seizure_free_contrast,
    ),
    Perturbation(
        "requested_mri_contrast",
        LABEL_CHANGING,
        "exectv2",
        "Add a pending MRI request that changes the current completed-result expectation.",
        add_requested_mri_contrast,
    ),
]


def gan_frequency_to_bullets(text: str, _: str) -> str:
    return text.replace("Current Medication:", "Current Medication:\n-").replace("Plan:", "Plan:\n-")


def gan_add_historical_frequency(text: str, _: str) -> str:
    trap = (
        "\n\nHistorical seizure frequency: Several years ago seizures were weekly, "
        "but this is not the current reporting interval."
    )
    return text.rstrip() + trap + "\n"


GAN_PERTURBATIONS = [
    Perturbation(
        "gan_frequency_bullets",
        GAN_FREQUENCY,
        "gan_2026",
        "Formatting stress test for Gan seizure-frequency examples.",
        gan_frequency_to_bullets,
    ),
    Perturbation(
        "gan_historical_frequency_trap",
        GAN_FREQUENCY,
        "gan_2026",
        "Add a historical competing frequency to Gan seizure-frequency examples.",
        gan_add_historical_frequency,
    ),
]


def write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")


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


def selected_ids(args: argparse.Namespace) -> list[str]:
    if args.documents:
        return args.documents
    if args.split:
        return load_split_ids(Path(args.splits), args.split, args.limit)
    ids = document_ids(Path(args.exect_root))
    return ids[: args.limit] if args.limit is not None else ids


def select_perturbations(ids: list[str] | None, candidates: list[Perturbation]) -> list[Perturbation]:
    if not ids:
        return candidates
    wanted = set(ids)
    selected = [item for item in candidates if item.id in wanted]
    missing = sorted(wanted - {item.id for item in selected})
    if missing:
        raise ValueError(f"unknown perturbation id(s): {', '.join(missing)}")
    return selected


def gan_expected_frequency(row: dict[str, Any]) -> dict[str, Any] | None:
    value = row.get("check__Seizure Frequency Number")
    if not isinstance(value, dict):
        return None
    frequency = value.get("seizure_frequency_number")
    reference = value.get("reference")
    if isinstance(frequency, list) and frequency:
        return {
            "current_seizure_frequency": frequency[0],
            "evidence_reference": reference[1] if isinstance(reference, list) and len(reference) > 1 else None,
        }
    return None


def load_gan_rows(path: Path, limit: int | None) -> list[dict[str, Any]]:
    data = json.loads(read_text(path))
    if not isinstance(data, list):
        raise ValueError(f"Gan data must be a JSON list: {path}")
    usable = [row for row in data if isinstance(row, dict) and row.get("row_ok") and gan_expected_frequency(row)]
    return usable[:limit] if limit is not None else usable


def write_split_file(path: Path, records: list[PerturbedRecord]) -> None:
    ids = [record.document_id for record in records]
    write_json(
        path,
        {
            "name": "robustness_generated_v1",
            "method": "generated perturbation corpus; all ids available through each split for runner compatibility",
            "counts": {"development": len(ids), "validation": len(ids), "test": len(ids)},
            "development": ids,
            "validation": ids,
            "test": ids,
        },
    )


def command_generate(args: argparse.Namespace) -> int:
    output_dir = Path(args.output_dir)
    corpus_dir = output_dir / "corpus"
    records: list[PerturbedRecord] = []
    perturbations = select_perturbations(args.perturbations, EXECT_PERTURBATIONS)

    for source_id in selected_ids(args):
        source_text = read_text(Path(args.exect_root) / f"{source_id}.txt")
        for perturbation in perturbations:
            document_id = f"{source_id}__{sanitize_id(perturbation.id)}"
            text = perturbation.apply(source_text, source_id)
            text_path = corpus_dir / f"{document_id}.txt"
            write_text(text_path, text)
            records.append(
                PerturbedRecord(
                    document_id=document_id,
                    source_document_id=source_id,
                    source_dataset="exectv2",
                    perturbation_id=perturbation.id,
                    label_effect=perturbation.label_effect,
                    text_path=str(text_path),
                    description=perturbation.description,
                )
            )

    if args.include_gan:
        gan_perturbations = select_perturbations(args.gan_perturbations, GAN_PERTURBATIONS)
        for row in load_gan_rows(Path(args.gan_path), args.gan_limit):
            source_id = f"GAN{row['source_row_index']}"
            source_text = row["clinic_date"]
            expected = gan_expected_frequency(row)
            for perturbation in gan_perturbations:
                document_id = f"{source_id}__{sanitize_id(perturbation.id)}"
                text_path = corpus_dir / f"{document_id}.txt"
                write_text(text_path, perturbation.apply(source_text, source_id))
                records.append(
                    PerturbedRecord(
                        document_id=document_id,
                        source_document_id=source_id,
                        source_dataset="gan_2026",
                        perturbation_id=perturbation.id,
                        label_effect=perturbation.label_effect,
                        text_path=str(text_path),
                        description=perturbation.description,
                        expected=expected,
                    )
                )

    write_json(output_dir / "perturbation_manifest.json", [asdict(record) for record in records])
    write_split_file(output_dir / "splits.json", records)
    print(f"wrote {len(records)} perturbed letters to {corpus_dir}")
    print(f"wrote {output_dir / 'perturbation_manifest.json'}")
    print(f"wrote {output_dir / 'splits.json'}")
    return 0


def run_command(command: list[str]) -> int:
    print("+ " + " ".join(command))
    completed = subprocess.run(command, check=False)
    return completed.returncode


def command_run_systems(args: argparse.Namespace) -> int:
    output_dir = Path(args.output_dir)
    corpus_dir = output_dir / "corpus"
    splits = output_dir / "splits.json"
    record_count = len(load_manifest(output_dir / "perturbation_manifest.json"))
    failures = 0
    if "S2" in args.systems:
        failures += int(
            run_command(
            [
                sys.executable,
                "src/direct_baselines.py",
                "run",
                "--provider",
                args.provider,
                "--model",
                args.model,
                "--exect-root",
                str(corpus_dir),
                "--splits",
                str(splits),
                "--split",
                "development",
                "--limit",
                str(record_count),
                "--baselines",
                "S2",
                "--output-dir",
                str(output_dir / "direct_baselines"),
            ]
            )
            != 0
        )
    event_systems = [system for system in args.systems if system in {"E2", "E3"}]
    if event_systems:
        failures += int(
            run_command(
            [
                sys.executable,
                "src/event_first.py",
                "run",
                "--provider",
                args.provider,
                "--model",
                args.model,
                "--exect-root",
                str(corpus_dir),
                "--splits",
                str(splits),
                "--split",
                "development",
                "--limit",
                str(record_count),
                "--pipelines",
                "E1",
                *event_systems,
                "--output-dir",
                str(output_dir / "event_first"),
            ]
            )
            != 0
        )
    if failures:
        print("one or more system runs reported failures; outputs written so robustness evaluation can count them")
    return 0


def perturbed_extraction_path(system: str, document_id: str, output_dir: Path) -> Path:
    if system == "S2":
        return output_dir / "direct_baselines" / "S2" / document_id / "canonical.json"
    if system == "E2":
        return output_dir / "event_first" / document_id / "e2_canonical.json"
    if system == "E3":
        return output_dir / "event_first" / document_id / "e3_canonical.json"
    raise ValueError(f"unsupported system: {system}")


def clean_extraction_path(system: str, source_document_id: str, args: argparse.Namespace) -> Path:
    if system == "S2":
        return Path(args.clean_direct_run_dir) / "S2" / source_document_id / "canonical.json"
    if system == "E2":
        return Path(args.clean_event_run_dir) / source_document_id / "e2_canonical.json"
    if system == "E3":
        return Path(args.clean_event_run_dir) / source_document_id / "e3_canonical.json"
    raise ValueError(f"unsupported system: {system}")


def load_manifest(path: Path) -> list[dict[str, Any]]:
    data = json.loads(read_text(path))
    if not isinstance(data, list):
        raise ValueError(f"manifest must be a JSON list: {path}")
    return [record for record in data if isinstance(record, dict)]


def validity_score(data: Any | None, source_text: str, schema_path: Path) -> dict[str, Any]:
    if data is None:
        return {"available": False, "schema_valid": False, "quote_validity_rate": None, "errors": ["missing output"]}
    errors = []
    try:
        validate_extraction(data, schema_path, require_present_evidence=True)
        schema_valid = True
    except Exception as exc:
        schema_valid = False
        errors.append(str(exc))
    quote_total, quote_failures = check_quote_validity(data, source_text)
    return {
        "available": True,
        "schema_valid": schema_valid,
        "quote_validity_rate": (quote_total - len(quote_failures)) / quote_total if quote_total else 1.0,
        "quote_count": quote_total,
        "invalid_quote_count": len(quote_failures),
        "errors": errors,
    }


def normalize_frequency(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip().lower().replace("-", " ")
    text = re.sub(r"[^a-z0-9.]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def gan_frequency_score(data: Any | None, expected: dict[str, Any] | None, source_text: str, schema_path: Path) -> dict[str, Any]:
    score = validity_score(data, source_text, schema_path)
    fields = data.get("fields", {}) if isinstance(data, dict) else {}
    predicted = normalize_frequency(fields.get("current_seizure_frequency", {}).get("value"))
    gold = normalize_frequency((expected or {}).get("current_seizure_frequency"))
    score.update({"predicted_frequency": predicted, "expected_frequency": gold, "frequency_correct": bool(gold and predicted == gold)})
    return score


def metric_delta_rows(
    system: str,
    perturbation_id: str,
    label_effect: str,
    robust_scores: list[dict[str, Any]],
    clean_scores: list[dict[str, Any]],
) -> dict[str, Any]:
    robust = flatten_summary(system, robust_scores)
    clean = flatten_summary(system, clean_scores) if clean_scores else {}
    row: dict[str, Any] = {
        "system": system,
        "perturbation_id": perturbation_id,
        "label_effect": label_effect,
        "documents": robust["documents_expected"],
        "available": robust["documents_available"],
    }
    metrics = [
        "schema_valid_rate",
        "quote_validity_rate",
        "medication_full_f1",
        "seizure_type_f1",
        "current_seizure_frequency_accuracy",
        "seizure_frequency_type_linkage_accuracy",
        "eeg_accuracy",
        "mri_accuracy",
        "epilepsy_diagnosis_accuracy",
    ]
    for metric in metrics:
        robust_value = robust.get(metric)
        clean_value = clean.get(metric)
        row[f"robust_{metric}"] = robust_value
        row[f"clean_{metric}"] = clean_value
        row[f"delta_{metric}"] = robust_value - clean_value if isinstance(robust_value, (int, float)) and isinstance(clean_value, (int, float)) else None
    return row


def aggregate_gan_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault((row["system"], row["perturbation_id"]), []).append(row)
    summaries = []
    for (system, perturbation_id), items in sorted(grouped.items()):
        available = [item for item in items if item["available"]]
        correct = [item for item in available if item["frequency_correct"]]
        quote_rates = [item["quote_validity_rate"] for item in available if isinstance(item.get("quote_validity_rate"), (int, float))]
        summaries.append(
            {
                "system": system,
                "perturbation_id": perturbation_id,
                "label_effect": GAN_FREQUENCY,
                "documents": len(items),
                "available": len(available),
                "schema_valid_rate": sum(1 for item in available if item["schema_valid"]) / len(available) if available else 0.0,
                "quote_validity_rate": sum(quote_rates) / len(quote_rates) if quote_rates else None,
                "frequency_accuracy": len(correct) / len(available) if available else None,
            }
        )
    return summaries


def command_evaluate(args: argparse.Namespace) -> int:
    output_dir = Path(args.output_dir)
    manifest = load_manifest(output_dir / "perturbation_manifest.json")
    gold = load_gold(Path(args.markup_root), Path(args.exect_root))
    systems = args.systems
    document_scores: dict[str, list[dict[str, Any]]] = {system: [] for system in systems}
    label_preserving_by_group: dict[tuple[str, str], list[dict[str, Any]]] = {}
    clean_by_group: dict[tuple[str, str], list[dict[str, Any]]] = {}
    validity_rows: list[dict[str, Any]] = []
    gan_rows: list[dict[str, Any]] = []

    for record in manifest:
        source_text = read_text(Path(record["text_path"]))
        for system in systems:
            data = load_json(perturbed_extraction_path(system, record["document_id"], output_dir))
            if record["source_dataset"] == "exectv2" and record["label_effect"] == LABEL_PRESERVING:
                document_gold = gold.get(record["source_document_id"])
                if document_gold is None:
                    continue
                score = score_document(data, source_text, document_gold, Path(args.schema))
                score.update(
                    {
                        "document_id": record["document_id"],
                        "source_document_id": record["source_document_id"],
                        "system": system,
                        "perturbation_id": record["perturbation_id"],
                        "label_effect": record["label_effect"],
                    }
                )
                document_scores[system].append(score)
                label_preserving_by_group.setdefault((system, record["perturbation_id"]), []).append(score)

                clean_data = load_json(clean_extraction_path(system, record["source_document_id"], args))
                if clean_data is not None:
                    clean_source = read_text(Path(args.exect_root) / f"{record['source_document_id']}.txt")
                    clean_score = score_document(clean_data, clean_source, document_gold, Path(args.schema))
                    clean_by_group.setdefault((system, record["perturbation_id"]), []).append(clean_score)
            elif record["source_dataset"] == "gan_2026":
                gan_score = gan_frequency_score(data, record.get("expected"), source_text, Path(args.schema))
                gan_score.update(
                    {
                        "document_id": record["document_id"],
                        "source_document_id": record["source_document_id"],
                        "system": system,
                        "perturbation_id": record["perturbation_id"],
                        "label_effect": record["label_effect"],
                    }
                )
                gan_rows.append(gan_score)
            else:
                validity = validity_score(data, source_text, Path(args.schema))
                validity.update(
                    {
                        "document_id": record["document_id"],
                        "source_document_id": record["source_document_id"],
                        "system": system,
                        "perturbation_id": record["perturbation_id"],
                        "label_effect": record["label_effect"],
                    }
                )
                validity_rows.append(validity)

    degradation_rows = [
        metric_delta_rows(system, perturbation_id, LABEL_PRESERVING, scores, clean_by_group.get((system, perturbation_id), []))
        for (system, perturbation_id), scores in sorted(label_preserving_by_group.items())
    ]
    write_json(output_dir / "robustness_document_scores.json", document_scores)
    write_json(output_dir / "label_changing_validity.json", validity_rows)
    write_json(output_dir / "gan_frequency_scores.json", gan_rows)
    write_json(
        output_dir / "robustness_summary.json",
        {
            "systems": systems,
            "label_preserving_degradation": degradation_rows,
            "label_changing_validity": validity_rows,
            "gan_frequency_summary": aggregate_gan_rows(gan_rows),
        },
    )
    write_csv(output_dir / "label_preserving_degradation.csv", degradation_rows)
    write_csv(output_dir / "gan_frequency_summary.csv", aggregate_gan_rows(gan_rows))
    print(f"wrote {output_dir / 'robustness_summary.json'}")
    print(f"wrote {output_dir / 'label_preserving_degradation.csv'}")
    return 0


def add_generate_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--exect-root", default=str(DEFAULT_EXECT_ROOT))
    parser.add_argument("--splits", default=str(DEFAULT_SPLITS))
    parser.add_argument("--split", default="validation", choices=["development", "validation", "test"])
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--documents", nargs="+")
    parser.add_argument("--perturbations", nargs="+")
    parser.add_argument("--include-gan", action="store_true")
    parser.add_argument("--gan-path", default=str(DEFAULT_GAN_PATH))
    parser.add_argument("--gan-limit", type=int, default=5)
    parser.add_argument("--gan-perturbations", nargs="+")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    generate = subparsers.add_parser("generate", help="Create a perturbed corpus and robustness manifest.")
    add_generate_args(generate)
    generate.set_defaults(func=command_generate)

    run_systems = subparsers.add_parser("run-systems", help="Run selected systems on the generated perturbed corpus.")
    run_systems.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    run_systems.add_argument("--systems", nargs="+", default=["S2", "E2", "E3"], choices=["S2", "E2", "E3"])
    run_systems.add_argument("--provider", default="stub", choices=["stub", "openai"])
    run_systems.add_argument("--model", default="gpt-4.1-mini")
    run_systems.set_defaults(func=command_run_systems)

    evaluate = subparsers.add_parser("evaluate", help="Score robustness outputs and write degradation tables.")
    evaluate.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    evaluate.add_argument("--systems", nargs="+", default=["S2", "E2", "E3"], choices=["S2", "E2", "E3"])
    evaluate.add_argument("--exect-root", default=str(DEFAULT_EXECT_ROOT))
    evaluate.add_argument("--markup-root", default=str(DEFAULT_MARKUP_ROOT))
    evaluate.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    evaluate.add_argument("--clean-direct-run-dir", default=str(DEFAULT_DIRECT_RUN_DIR))
    evaluate.add_argument("--clean-event-run-dir", default=str(DEFAULT_EVENT_RUN_DIR))
    evaluate.set_defaults(func=command_evaluate)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
