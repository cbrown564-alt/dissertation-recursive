#!/usr/bin/env python3
"""Run Phase 4 recovery prompt experiments.

S4 runs short task-specific direct prompts and merges their outputs into the
canonical extraction schema. S5 adds a candidate-verification pass before the
same canonical merge.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import time
from pathlib import Path
from typing import Any

from direct_baselines import (
    ParseResult,
    append_jsonl,
    call_openai,
    empty_investigation,
    empty_scalar,
    load_split_ids,
    normalize_contract_aliases,
    parse_json_response,
    sentence_table,
    validate_and_score,
    write_json,
    write_text,
)
from intake import DEFAULT_EXECT_ROOT, DEFAULT_SPLITS, preprocess_document, read_text
from validate_extraction import DEFAULT_SCHEMA


PROMPT_DIR = Path("prompts/recovery")
DEFAULT_OUTPUT_DIR = Path("runs/recovery/phase4_prompt_contract")
DEFAULT_PROMPT_MATRIX = Path("runs/recovery/prompt_matrix.json")

S4_PIPELINE_ID = "S4_benchmark_direct_task_prompts"
S5_PIPELINE_ID = "S5_benchmark_direct_with_verifier"

TASKS: dict[str, dict[str, Any]] = {
    "medication_names": {
        "prompt": PROMPT_DIR / "s4_medication_names.md",
        "benchmark_aligned": True,
        "canonical_targets": ["fields.current_anti_seizure_medications[].name"],
    },
    "medication_full_tuple": {
        "prompt": PROMPT_DIR / "s4_medication_full_tuple.md",
        "benchmark_aligned": False,
        "canonical_targets": ["fields.current_anti_seizure_medications[]"],
    },
    "seizure_type": {
        "prompt": PROMPT_DIR / "s4_seizure_type.md",
        "benchmark_aligned": True,
        "canonical_targets": ["fields.seizure_types[]"],
    },
    "seizure_frequency": {
        "prompt": PROMPT_DIR / "s4_seizure_frequency.md",
        "benchmark_aligned": False,
        "canonical_targets": ["fields.current_seizure_frequency"],
    },
    "diagnosis_type": {
        "prompt": PROMPT_DIR / "s4_diagnosis_type.md",
        "benchmark_aligned": True,
        "canonical_targets": ["fields.epilepsy_diagnosis"],
    },
    "associated_symptoms": {
        "prompt": PROMPT_DIR / "s4_associated_symptoms.md",
        "benchmark_aligned": True,
        "canonical_targets": ["metadata.recovery.associated_symptoms"],
        "optional_extension": True,
    },
}


def evidence_or_none(value: Any) -> list[dict[str, Any]] | None:
    evidence = value.get("evidence") if isinstance(value, dict) else None
    if not isinstance(evidence, dict) or not evidence.get("quote"):
        return None
    return [
        {
            "quote": evidence.get("quote"),
            "sentence_id": evidence.get("sentence_id"),
            "char_start": evidence.get("char_start"),
            "char_end": evidence.get("char_end"),
        }
    ]


def event_evidence(value: dict[str, Any]) -> dict[str, Any]:
    evidence = evidence_or_none(value)
    if evidence:
        return evidence[0]
    return {"quote": ""}


def empty_seizure_frequency() -> dict[str, Any]:
    field = empty_scalar()
    field["temporal_scope"] = None
    field["seizure_type"] = None
    return field


def current_medication(candidate: dict[str, Any], event_id: str) -> dict[str, Any]:
    return {
        "name": candidate.get("name"),
        "dose": candidate.get("dose"),
        "dose_unit": candidate.get("dose_unit"),
        "frequency": candidate.get("frequency"),
        "status": "current",
        "missingness": "present",
        "temporality": "current",
        "reason_stopped": None,
        "evidence": evidence_or_none(candidate),
        "evidence_event_ids": [event_id],
        "confidence": candidate.get("confidence"),
    }


def scalar_field(candidate: dict[str, Any], event_id: str, temporality: str = "current") -> dict[str, Any]:
    return {
        "value": candidate.get("value"),
        "missingness": "present",
        "temporality": candidate.get("temporality") or temporality,
        "evidence": evidence_or_none(candidate),
        "evidence_event_ids": [event_id],
        "confidence": candidate.get("confidence"),
    }


def candidate_list(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return []
    candidates = payload.get("candidates")
    if isinstance(candidates, list):
        return [item for item in candidates if isinstance(item, dict)]
    candidate = payload.get("candidate")
    return [candidate] if isinstance(candidate, dict) else []


def build_task_prompt(task: str, document: dict[str, Any]) -> str:
    return "\n\n".join(
        [
            read_text(TASKS[task]["prompt"]),
            "## Sentence List",
            sentence_table(document["sentences"]),
            "## Source Letter",
            document["text"],
        ]
    )


def build_verifier_prompt(document: dict[str, Any], candidates: list[dict[str, Any]]) -> str:
    return "\n\n".join(
        [
            read_text(PROMPT_DIR / "s5_candidate_verifier.md"),
            "## Source Letter",
            document["text"],
            "## Extracted Candidates",
            json.dumps(candidates, indent=2, ensure_ascii=False),
        ]
    )


def stub_task_response(task: str) -> str:
    if task in {"seizure_frequency", "diagnosis_type"}:
        return json.dumps({"task": task, "candidate": None}, indent=2)
    return json.dumps({"task": task, "candidates": []}, indent=2)


def get_response(args: argparse.Namespace, prompt: str, stub_response: str) -> tuple[str, float, str]:
    started = time.perf_counter()
    if args.provider == "stub":
        return stub_response, (time.perf_counter() - started) * 1000, "stub"
    if args.provider == "openai":
        raw = call_openai(prompt, args.model)
        return raw, (time.perf_counter() - started) * 1000, args.model
    raise ValueError(f"unsupported provider: {args.provider}")


def parse_record(parse: ParseResult) -> dict[str, Any]:
    return {
        "parse_success": parse.parse_success,
        "repair_attempted": parse.repair_attempted,
        "repair_succeeded": parse.repair_succeeded,
        "error": parse.error,
    }


def run_task(args: argparse.Namespace, document: dict[str, Any], task: str, root: Path) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    prompt = build_task_prompt(task, document)
    prompt_path = root / "tasks" / task / "prompt.txt"
    raw_path = root / "tasks" / task / "raw.json"
    parsed_path = root / "tasks" / task / "parsed.json"
    write_text(prompt_path, prompt)

    if raw_path.exists() and not args.refresh:
        raw_response = read_text(raw_path)
        latency_ms = 0.0
        model_name = args.model if args.provider == "openai" else "stub"
    else:
        raw_response, latency_ms, model_name = get_response(args, prompt, stub_task_response(task))
        write_text(raw_path, raw_response)

    parse = parse_json_response(raw_response)
    if parse.data is not None:
        write_json(parsed_path, parse.data)

    return parse.data if isinstance(parse.data, dict) else None, {
        "task": task,
        "prompt_path": str(prompt_path),
        "raw_response_path": str(raw_path),
        "parsed_path": str(parsed_path) if parse.data is not None else None,
        "model": model_name,
        "latency_ms": latency_ms,
        "parse": parse_record(parse),
    }


def flatten_candidates(task_outputs: dict[str, Any]) -> list[dict[str, Any]]:
    flattened: list[dict[str, Any]] = []
    for task, payload in task_outputs.items():
        for index, candidate in enumerate(candidate_list(payload)):
            item = dict(candidate)
            item["task"] = task
            item["candidate_index"] = index
            flattened.append(item)
    return flattened


def apply_verifier(task_outputs: dict[str, Any], verifier_payload: Any) -> dict[str, list[dict[str, Any]]]:
    accepted = {task: [] for task in TASKS}
    decisions = verifier_payload.get("decisions") if isinstance(verifier_payload, dict) else None
    if not isinstance(decisions, list):
        for task, payload in task_outputs.items():
            accepted[task] = candidate_list(payload)
        return accepted

    original = {task: candidate_list(payload) for task, payload in task_outputs.items()}
    for decision in decisions:
        if not isinstance(decision, dict) or decision.get("decision") != "keep":
            continue
        task = decision.get("task")
        index = decision.get("candidate_index")
        if not isinstance(task, str) or not isinstance(index, int):
            continue
        candidates = original.get(task, [])
        if index < 0 or index >= len(candidates):
            continue
        merged = dict(candidates[index])
        normalized = decision.get("normalized")
        if isinstance(normalized, dict):
            merged.update({key: value for key, value in normalized.items() if value is not None})
        if isinstance(decision.get("evidence"), dict):
            merged["evidence"] = decision["evidence"]
        accepted.setdefault(task, []).append(merged)
    return accepted


def unverified_candidates(task_outputs: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    return {task: candidate_list(payload) for task, payload in task_outputs.items()}


def merge_canonical(
    document_id: str,
    pipeline_id: str,
    candidates_by_task: dict[str, list[dict[str, Any]]],
    model_name: str,
    task_records: list[dict[str, Any]],
    verifier_record: dict[str, Any] | None,
) -> dict[str, Any]:
    fields: dict[str, Any] = {
        "current_anti_seizure_medications": [],
        "previous_anti_seizure_medications": [],
        "current_seizure_frequency": empty_seizure_frequency(),
        "seizure_types": [],
        "eeg": empty_investigation(),
        "mri": empty_investigation(),
        "epilepsy_diagnosis": empty_scalar(),
    }
    events: list[dict[str, Any]] = []

    full_by_name = {item.get("name"): item for item in candidates_by_task.get("medication_full_tuple", []) if item.get("name")}
    medication_candidates = candidates_by_task.get("medication_full_tuple", []) or candidates_by_task.get("medication_names", [])
    for index, candidate in enumerate(medication_candidates, start=1):
        if not candidate.get("name"):
            continue
        full = full_by_name.get(candidate.get("name"), candidate)
        event_id = f"ev_s4_med_{index}"
        fields["current_anti_seizure_medications"].append(current_medication(full, event_id))
        events.append(
            {
                "id": event_id,
                "category": "medication",
                "temporality": "current",
                "status": "current",
                "value": full.get("name"),
                "medication_name": full.get("name"),
                "dose": full.get("dose"),
                "dose_unit": full.get("dose_unit"),
                "frequency": full.get("frequency"),
                "reason_stopped": None,
                "evidence": event_evidence(full),
            }
        )

    for index, candidate in enumerate(candidates_by_task.get("seizure_type", []), start=1):
        if not candidate.get("value"):
            continue
        event_id = f"ev_s4_type_{index}"
        fields["seizure_types"].append(scalar_field(candidate, event_id, temporality="uncertain"))
        events.append(
            {
                "id": event_id,
                "category": "seizure_type",
                "temporality": candidate.get("temporality") or "uncertain",
                "status": None,
                "value": candidate.get("value"),
                "evidence": event_evidence(candidate),
            }
        )

    frequency_candidates = candidates_by_task.get("seizure_frequency", [])
    if frequency_candidates:
        candidate = frequency_candidates[0]
        event_id = "ev_s4_freq_1"
        frequency = scalar_field(candidate, event_id)
        frequency["temporal_scope"] = candidate.get("temporal_scope")
        frequency["seizure_type"] = candidate.get("seizure_type")
        fields["current_seizure_frequency"] = frequency
        events.append(
            {
                "id": event_id,
                "category": "seizure_frequency",
                "temporality": "current",
                "status": None,
                "value": candidate.get("value"),
                "temporal_scope": candidate.get("temporal_scope"),
                "seizure_type": candidate.get("seizure_type"),
                "evidence": event_evidence(candidate),
            }
        )

    diagnosis_candidates = candidates_by_task.get("diagnosis_type", [])
    if diagnosis_candidates:
        candidate = diagnosis_candidates[0]
        if candidate.get("value"):
            event_id = "ev_s4_dx_1"
            fields["epilepsy_diagnosis"] = scalar_field(candidate, event_id, temporality="current")
            events.append(
                {
                    "id": event_id,
                    "category": "diagnosis",
                    "temporality": candidate.get("temporality") or "current",
                    "status": None,
                    "value": candidate.get("value"),
                    "evidence": event_evidence(candidate),
                }
            )

    canonical = {
        "document_id": document_id,
        "pipeline_id": pipeline_id,
        "fields": fields,
        "events": events,
        "metadata": {
            "model": model_name,
            "format": "json",
            "latency_ms": sum(record.get("latency_ms", 0.0) for record in task_records)
            + (verifier_record or {}).get("latency_ms", 0.0),
            "input_tokens": 0,
            "output_tokens": 0,
            "repair_attempted": any(record.get("parse", {}).get("repair_attempted") for record in task_records),
            "repair_succeeded": any(record.get("parse", {}).get("repair_succeeded") for record in task_records),
            "recovery": {
                "task_records": task_records,
                "verifier_record": verifier_record,
                "associated_symptoms": candidates_by_task.get("associated_symptoms", []),
            },
        },
    }
    return normalize_contract_aliases(canonical, document_id, pipeline_id)


def run_verifier(args: argparse.Namespace, document: dict[str, Any], root: Path, candidates: list[dict[str, Any]]) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    prompt = build_verifier_prompt(document, candidates)
    prompt_path = root / "verifier" / "prompt.txt"
    raw_path = root / "verifier" / "raw.json"
    parsed_path = root / "verifier" / "parsed.json"
    write_text(prompt_path, prompt)
    stub = json.dumps({"decisions": []}, indent=2)
    if raw_path.exists() and not args.refresh:
        raw_response = read_text(raw_path)
        latency_ms = 0.0
        model_name = args.model if args.provider == "openai" else "stub"
    else:
        raw_response, latency_ms, model_name = get_response(args, prompt, stub)
        write_text(raw_path, raw_response)
    parse = parse_json_response(raw_response)
    if parse.data is not None:
        write_json(parsed_path, parse.data)
    return parse.data if isinstance(parse.data, dict) else None, {
        "prompt_path": str(prompt_path),
        "raw_response_path": str(raw_path),
        "parsed_path": str(parsed_path) if parse.data is not None else None,
        "model": model_name,
        "latency_ms": latency_ms,
        "parse": parse_record(parse),
    }


def run_one(args: argparse.Namespace, document_id: str, system: str) -> dict[str, Any]:
    document = preprocess_document(document_id, Path(args.exect_root))
    root = Path(args.output_dir) / system / document_id
    task_outputs: dict[str, Any] = {}
    task_records = []
    for task in args.tasks:
        payload, record = run_task(args, document, task, root)
        if payload is not None:
            task_outputs[task] = payload
        task_records.append(record)

    verifier_record = None
    verifier_payload = None
    if system == "S5":
        flattened = flatten_candidates(task_outputs)
        verifier_payload, verifier_record = run_verifier(args, document, root, flattened)
        candidates_by_task = apply_verifier(task_outputs, verifier_payload)
    else:
        candidates_by_task = unverified_candidates(task_outputs)

    pipeline_id = S5_PIPELINE_ID if system == "S5" else S4_PIPELINE_ID
    model_name = args.model if args.provider == "openai" else "stub"
    canonical = merge_canonical(document_id, pipeline_id, candidates_by_task, model_name, task_records, verifier_record)
    canonical_path = root / "canonical.json"
    write_json(canonical_path, canonical)
    scores = validate_and_score(canonical, document["text"], Path(args.schema), require_present_evidence=True)

    record = {
        "document_id": document_id,
        "system": system,
        "repeat": getattr(args, "repeat_index", 1),
        "pipeline_id": pipeline_id,
        "provider": args.provider,
        "model": model_name,
        "canonical_output_path": str(canonical_path),
        "task_outputs": task_outputs,
        "verifier_output": verifier_payload,
        "scores": scores,
    }
    append_jsonl(Path(args.output_dir) / "recovery_runs.jsonl", record)
    return record


def command_run(args: argparse.Namespace) -> int:
    if args.repeats > 1:
        manifest = {
            "split": args.split,
            "systems": args.systems,
            "tasks": args.tasks,
            "repeats": args.repeats,
            "provider": args.provider,
            "model": args.model,
            "repeat_roots": [],
        }
        failures = 0
        base_output_dir = Path(args.output_dir)
        for repeat in range(1, args.repeats + 1):
            repeat_args = argparse.Namespace(**vars(args))
            repeat_args.repeats = 1
            repeat_args.repeat_index = repeat
            repeat_args.output_dir = str(base_output_dir / f"repeat_{repeat:02d}")
            manifest["repeat_roots"].append(repeat_args.output_dir)
            failures += command_run(repeat_args)
        write_json(base_output_dir / "repeat_manifest.json", manifest)
        print(f"wrote {base_output_dir / 'repeat_manifest.json'}")
        return 1 if failures else 0

    ids = load_split_ids(Path(args.splits), args.split, args.limit)
    jobs = [(document_id, system) for document_id in ids for system in args.systems]
    failures = 0
    max_workers = max(1, args.max_workers)
    if max_workers == 1:
        records = [run_one(args, document_id, system) for document_id, system in jobs]
    else:
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(run_one, args, document_id, system) for document_id, system in jobs]
            records = [future.result() for future in concurrent.futures.as_completed(futures)]
    for record in records:
        scores = record["scores"] or {}
        ok = bool(scores.get("schema_valid") and scores.get("project_constraints_valid"))
        print(f"{'pass' if ok else 'fail'}: {record['system']} {record['document_id']}")
        failures += 0 if ok else 1
    return 1 if failures else 0


def command_prepare(args: argparse.Namespace) -> int:
    ids = load_split_ids(Path(args.splits), args.split, args.limit)
    for document_id in ids:
        document = preprocess_document(document_id, Path(args.exect_root))
        for system in args.systems:
            root = Path(args.output_dir) / system / document_id
            for task in args.tasks:
                path = root / "tasks" / task / "prompt.txt"
                write_text(path, build_task_prompt(task, document))
                print(f"wrote {path}")
            if system == "S5":
                path = root / "verifier" / "prompt.empty_candidates.txt"
                write_text(path, build_verifier_prompt(document, []))
                print(f"wrote {path}")
    return 0


def command_matrix(args: argparse.Namespace) -> int:
    matrix = {
        "phase": 4,
        "systems": {
            "S4": {
                "description": "Benchmark-style short direct prompts merged into canonical JSON.",
                "pipeline_id": S4_PIPELINE_ID,
                "tasks": list(TASKS),
            },
            "S5": {
                "description": "S4 plus source-grounded candidate verifier before canonical merge.",
                "pipeline_id": S5_PIPELINE_ID,
                "tasks": list(TASKS),
                "verifier_prompt": str(PROMPT_DIR / "s5_candidate_verifier.md"),
            },
        },
        "tasks": {
            task: {
                "prompt": str(config["prompt"]),
                "benchmark_aligned": config["benchmark_aligned"],
                "canonical_targets": config["canonical_targets"],
                "optional_extension": bool(config.get("optional_extension")),
            }
            for task, config in TASKS.items()
        },
        "held_out_policy": "Use development/validation only during recovery; do not tune on test.",
    }
    write_json(Path(args.output), matrix)
    print(f"wrote {args.output}")
    return 0


def add_common_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--exect-root", default=str(DEFAULT_EXECT_ROOT))
    parser.add_argument("--splits", default=str(DEFAULT_SPLITS))
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--split", default="development", choices=["development", "validation", "test"])
    parser.add_argument("--limit", type=int)
    parser.add_argument("--max-workers", type=int, default=1)
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--systems", nargs="+", default=["S4", "S5"], choices=["S4", "S5"])
    parser.add_argument("--tasks", nargs="+", default=list(TASKS), choices=list(TASKS))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    run = subparsers.add_parser("run", help="Run S4/S5 recovery experiments.")
    add_common_arguments(run)
    run.add_argument("--provider", default="stub", choices=["stub", "openai"])
    run.add_argument("--model", default="gpt-4.1-mini")
    run.set_defaults(func=command_run)

    prepare = subparsers.add_parser("prepare", help="Write prompts without calling a provider.")
    add_common_arguments(prepare)
    prepare.set_defaults(func=command_prepare)

    matrix = subparsers.add_parser("matrix", help="Write the Phase 4 prompt matrix artifact.")
    matrix.add_argument("--output", default=str(DEFAULT_PROMPT_MATRIX))
    matrix.set_defaults(func=command_matrix)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
