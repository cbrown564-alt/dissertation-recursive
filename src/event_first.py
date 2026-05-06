#!/usr/bin/env python3
"""Run Milestone 4 event-first extraction and aggregation pipelines."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

from direct_baselines import (
    ParseResult,
    append_jsonl,
    call_openai,
    compact_schema_text,
    empty_investigation,
    empty_scalar,
    load_split_ids,
    parse_json_response,
    sentence_table,
    validate_and_score,
    write_json,
    write_text,
)
from intake import DEFAULT_EXECT_ROOT, DEFAULT_SPLITS, preprocess_document, read_text
from validate_extraction import (
    DEFAULT_SCHEMA,
    EVENT_CATEGORY,
    EVENT_STATUS,
    TEMPORALITY,
    ValidationError,
    check_quote_validity,
    validate_event,
)


PROMPT_DIR = Path("prompts/event_first")
DEFAULT_OUTPUT_DIR = Path("runs/event_first")

E1_PIPELINE_ID = "E1_event_extraction"
E2_PIPELINE_ID = "E2_deterministic_event_aggregation"
E3_PIPELINE_ID = "E3_constrained_event_aggregation"


def build_e1_prompt(document: dict[str, Any]) -> str:
    return "\n\n".join(
        [
            read_text(PROMPT_DIR / "e1_event_extraction.md"),
            "## Event Schema Notes",
            event_schema_notes(),
            "## Sentence List",
            sentence_table(document["sentences"]),
            "## Source Letter",
            document["text"],
        ]
    )


def build_e3_prompt(document_id: str, events: list[dict[str, Any]], schema_path: Path) -> str:
    return "\n\n".join(
        [
            read_text(PROMPT_DIR / "e3_constrained_aggregation.md"),
            "## Canonical JSON Schema",
            compact_schema_text(schema_path),
            "## Document ID",
            document_id,
            "## Event List",
            json.dumps(events, indent=2, ensure_ascii=False),
        ]
    )


def event_schema_notes() -> str:
    statuses = sorted(item for item in EVENT_STATUS if item is not None) + [None]
    return json.dumps(
        {
            "category": sorted(EVENT_CATEGORY),
            "temporality": sorted(TEMPORALITY),
            "status": statuses,
            "investigation_type": ["EEG", "MRI", None],
            "investigation_result": ["normal", "abnormal", "not_stated", "uncertain", None],
        },
        indent=2,
        ensure_ascii=False,
    )


def stub_e1_response(document_id: str, latency_ms: float) -> str:
    return json.dumps(
        {
            "document_id": document_id,
            "pipeline_id": E1_PIPELINE_ID,
            "events": [],
            "metadata": {
                "model": "stub",
                "format": "json",
                "latency_ms": latency_ms,
                "input_tokens": 0,
                "output_tokens": 0,
                "repair_attempted": False,
                "repair_succeeded": False,
            },
        },
        indent=2,
        ensure_ascii=False,
    )


def get_model_response(args: argparse.Namespace, prompt: str, document_id: str) -> tuple[str, float, str]:
    started = time.perf_counter()
    if args.provider == "stub":
        latency_ms = (time.perf_counter() - started) * 1000
        return stub_e1_response(document_id, latency_ms), latency_ms, "stub"
    if args.provider == "openai":
        response = call_openai(prompt, args.model)
        latency_ms = (time.perf_counter() - started) * 1000
        return response, latency_ms, args.model
    raise ValueError(f"unsupported provider: {args.provider}")


def normalize_event_payload(data: Any, document_id: str, model_name: str, latency_ms: float, parse: ParseResult) -> dict[str, Any]:
    if isinstance(data, list):
        data = {"document_id": document_id, "pipeline_id": E1_PIPELINE_ID, "events": data, "metadata": {}}
    if not isinstance(data, dict):
        raise ValidationError("E1 output must be an object or event array")
    data.setdefault("document_id", document_id)
    data.setdefault("pipeline_id", E1_PIPELINE_ID)
    data.setdefault("events", [])
    data.setdefault("metadata", {})
    data["metadata"].update(
        {
            "model": model_name,
            "format": "json",
            "latency_ms": latency_ms,
            "repair_attempted": parse.repair_attempted,
            "repair_succeeded": parse.repair_succeeded,
        }
    )
    return data


def validate_event_payload(data: dict[str, Any], source_text: str) -> dict[str, Any]:
    result: dict[str, Any] = {
        "event_constraints_valid": False,
        "quote_validity": None,
        "validation_errors": [],
    }
    try:
        if not isinstance(data.get("events"), list):
            raise ValidationError("$.events must be an array")
        event_ids = set()
        for index, event in enumerate(data["events"]):
            validate_event(event, f"$.events[{index}]")
            if event["id"] in event_ids:
                raise ValidationError(f"duplicate event id: {event['id']}")
            event_ids.add(event["id"])
        result["event_constraints_valid"] = True
    except ValidationError as exc:
        result["validation_errors"].append(str(exc))

    quote_total, quote_failures = check_quote_validity({"events": data.get("events", [])}, source_text)
    result["quote_validity"] = {
        "quote_count": quote_total,
        "valid_quote_count": quote_total - len(quote_failures),
        "invalid_quote_count": len(quote_failures),
        "invalid_quote_paths": quote_failures,
        "pass": len(quote_failures) == 0,
    }
    return result


def field_from_event(event: dict[str, Any], value: Any | None = None, temporality: str | None = None) -> dict[str, Any]:
    return {
        "value": value if value is not None else event.get("value"),
        "missingness": "present",
        "temporality": temporality or event.get("temporality", "uncertain"),
        "evidence": [event["evidence"]],
        "evidence_event_ids": [event["id"]],
        "confidence": None,
    }


def medication_from_event(event: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": event.get("medication_name") or event.get("value"),
        "dose": event.get("dose"),
        "dose_unit": event.get("dose_unit"),
        "frequency": event.get("frequency"),
        "status": event.get("status") or "current",
        "missingness": "present",
        "temporality": event.get("temporality", "current"),
        "reason_stopped": event.get("reason_stopped"),
        "evidence": [event["evidence"]],
        "evidence_event_ids": [event["id"]],
        "confidence": None,
    }


def investigation_from_event(event: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": event.get("status") or "completed",
        "result": event.get("result") or "not_stated",
        "missingness": "present",
        "temporality": event.get("temporality", "completed"),
        "evidence": [event["evidence"]],
        "evidence_event_ids": [event["id"]],
        "confidence": None,
    }


def empty_seizure_frequency() -> dict[str, Any]:
    field = empty_scalar()
    field["temporal_scope"] = None
    field["seizure_type"] = None
    return field


def no_support(log: dict[str, Any], path: str, reason: str) -> None:
    log["missingness_decisions"].append({"field": path, "decision": "not_stated", "reason": reason})
    log["final_fields_without_event_support"].append(path)


def choose_latest_current(events: list[dict[str, Any]]) -> dict[str, Any] | None:
    current = [event for event in events if event.get("temporality") == "current"]
    if current:
        return current[-1]
    non_historical = [event for event in events if event.get("temporality") not in {"historical", "family_history", "hypothetical"}]
    return non_historical[-1] if non_historical else None


def aggregate_events(document_id: str, events: list[dict[str, Any]], model_name: str = "deterministic") -> tuple[dict[str, Any], dict[str, Any]]:
    log: dict[str, Any] = {
        "selected_event_ids": {},
        "ignored_event_ids": [],
        "conflict_decisions": [],
        "missingness_decisions": [],
        "final_fields_without_event_support": [],
        "extension_non_current_medications": [],
        "extension_investigation_statuses": [],
    }

    fields: dict[str, Any] = {
        "current_anti_seizure_medications": [],
        "previous_anti_seizure_medications": [],
        "current_seizure_frequency": empty_seizure_frequency(),
        "seizure_types": [],
        "eeg": empty_investigation(),
        "mri": empty_investigation(),
        "epilepsy_diagnosis": empty_scalar(),
    }

    medication_events = [event for event in events if event.get("category") == "medication"]
    for event in medication_events:
        status = event.get("status")
        if event.get("temporality") == "current" and status == "current":
            fields["current_anti_seizure_medications"].append(medication_from_event(event))
            log["selected_event_ids"].setdefault("current_anti_seizure_medications", []).append(event["id"])
        elif status in {"previous", "stopped"} or event.get("temporality") == "historical":
            previous = medication_from_event(event)
            previous["status"] = status if status in {"previous", "stopped"} else "previous"
            previous["temporality"] = "historical"
            fields["previous_anti_seizure_medications"].append(previous)
            log["selected_event_ids"].setdefault("previous_anti_seizure_medications", []).append(event["id"])
            if status != "previous":
                log["extension_non_current_medications"].append(event)
        else:
            log["ignored_event_ids"].append(event["id"])
            if status != "current":
                log["extension_non_current_medications"].append(event)

    seizure_frequency_events = [event for event in events if event.get("category") == "seizure_frequency"]
    selected_frequency = choose_latest_current(seizure_frequency_events)
    if selected_frequency:
        frequency = field_from_event(selected_frequency, temporality=selected_frequency.get("temporality", "uncertain"))
        frequency["temporal_scope"] = selected_frequency.get("temporal_scope")
        frequency["seizure_type"] = selected_frequency.get("seizure_type")
        fields["current_seizure_frequency"] = frequency
        log["selected_event_ids"]["current_seizure_frequency"] = [selected_frequency["id"]]
        for event in seizure_frequency_events:
            if event["id"] != selected_frequency["id"]:
                log["ignored_event_ids"].append(event["id"])
    else:
        no_support(log, "current_seizure_frequency", "no seizure-frequency event")

    for event in events:
        if event.get("category") == "seizure_type":
            fields["seizure_types"].append(field_from_event(event))
            log["selected_event_ids"].setdefault("seizure_types", []).append(event["id"])

    investigation_events = [event for event in events if event.get("category") == "investigation"]
    for investigation_type, field_name in [("EEG", "eeg"), ("MRI", "mri")]:
        candidates = [event for event in investigation_events if event.get("investigation_type") == investigation_type]
        result_events = [
            event
            for event in candidates
            if event.get("status") == "completed" and event.get("result") in {"normal", "abnormal", "uncertain"}
        ]
        if result_events:
            selected = result_events[-1]
            fields[field_name] = investigation_from_event(selected)
            log["selected_event_ids"][field_name] = [selected["id"]]
            for event in candidates:
                if event["id"] != selected["id"]:
                    log["ignored_event_ids"].append(event["id"])
                    if event.get("status") != "completed" or event.get("result") in {None, "not_stated"}:
                        log["extension_investigation_statuses"].append(event)
        else:
            no_support(log, field_name, f"no completed {investigation_type} result event")
            for event in candidates:
                log["ignored_event_ids"].append(event["id"])
                log["extension_investigation_statuses"].append(event)

    diagnosis_events = [event for event in events if event.get("category") == "diagnosis" and event.get("temporality") != "family_history"]
    if diagnosis_events:
        selected = diagnosis_events[-1]
        fields["epilepsy_diagnosis"] = field_from_event(selected)
        log["selected_event_ids"]["epilepsy_diagnosis"] = [selected["id"]]
        for event in diagnosis_events[:-1]:
            log["ignored_event_ids"].append(event["id"])
            log["conflict_decisions"].append(
                {
                    "field": "epilepsy_diagnosis",
                    "selected_event_id": selected["id"],
                    "ignored_event_id": event["id"],
                    "reason": "later diagnosis event selected by deterministic ordering",
                }
            )
    else:
        no_support(log, "epilepsy_diagnosis", "no patient-level diagnosis event")

    canonical = {
        "document_id": document_id,
        "pipeline_id": E2_PIPELINE_ID,
        "fields": fields,
        "events": events,
        "metadata": {
            "model": model_name,
            "format": "json",
            "latency_ms": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "repair_attempted": False,
            "repair_succeeded": False,
            "aggregation": log,
        },
    }
    return canonical, log


def run_e1(args: argparse.Namespace, document: dict[str, Any], run_root: Path) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    prompt = build_e1_prompt(document)
    prompt_path = run_root / "e1_prompt.txt"
    raw_path = run_root / "e1_raw.json"
    events_path = run_root / "e1_events.json"
    write_text(prompt_path, prompt)

    raw_response, latency_ms, model_name = get_model_response(args, prompt, document["document_id"])
    write_text(raw_path, raw_response)
    parse = parse_json_response(raw_response)

    payload = None
    scores = None
    if parse.data is not None:
        try:
            payload = normalize_event_payload(parse.data, document["document_id"], model_name, latency_ms, parse)
            write_json(events_path, payload)
            scores = validate_event_payload(payload, document["text"])
        except ValidationError as exc:
            scores = {"event_constraints_valid": False, "quote_validity": None, "validation_errors": [str(exc)]}

    record = {
        "document_id": document["document_id"],
        "pipeline": "E1",
        "pipeline_id": E1_PIPELINE_ID,
        "provider": args.provider,
        "model": model_name,
        "prompt_path": str(prompt_path),
        "raw_response_path": str(raw_path),
        "event_output_path": str(events_path) if payload is not None else None,
        "parse": {
            "parse_success": parse.parse_success,
            "repair_attempted": parse.repair_attempted,
            "repair_succeeded": parse.repair_succeeded,
            "error": parse.error,
        },
        "scores": scores,
    }
    return payload, record


def run_e2(args: argparse.Namespace, document: dict[str, Any], events: list[dict[str, Any]], run_root: Path) -> dict[str, Any]:
    canonical, log = aggregate_events(document["document_id"], events)
    canonical_path = run_root / "e2_canonical.json"
    log_path = run_root / "e2_aggregation_log.json"
    write_json(canonical_path, canonical)
    write_json(log_path, log)
    scores = validate_and_score(canonical, document["text"], Path(args.schema), require_present_evidence=True)
    return {
        "document_id": document["document_id"],
        "pipeline": "E2",
        "pipeline_id": E2_PIPELINE_ID,
        "provider": "deterministic",
        "model": "deterministic",
        "canonical_output_path": str(canonical_path),
        "aggregation_log_path": str(log_path),
        "scores": scores,
    }


def run_e3(args: argparse.Namespace, document: dict[str, Any], events: list[dict[str, Any]], run_root: Path) -> dict[str, Any]:
    prompt = build_e3_prompt(document["document_id"], events, Path(args.schema))
    prompt_path = run_root / "e3_prompt.txt"
    raw_path = run_root / "e3_raw.json"
    canonical_path = run_root / "e3_canonical.json"
    write_text(prompt_path, prompt)

    started = time.perf_counter()
    if args.provider == "stub":
        canonical, log = aggregate_events(document["document_id"], events, model_name="stub_constrained_fallback")
        canonical["pipeline_id"] = E3_PIPELINE_ID
        canonical["metadata"]["aggregation"] = log
        raw_response = json.dumps(canonical, indent=2, ensure_ascii=False)
        latency_ms = (time.perf_counter() - started) * 1000
        model_name = "stub"
    else:
        raw_response = call_openai(prompt, args.model)
        latency_ms = (time.perf_counter() - started) * 1000
        model_name = args.model
    write_text(raw_path, raw_response)

    parse = parse_json_response(raw_response)
    scores = None
    if parse.data is not None:
        if isinstance(parse.data, dict):
            parse.data.setdefault("metadata", {})
            parse.data["metadata"].update(
                {
                    "model": model_name,
                    "format": "constrained_json",
                    "latency_ms": latency_ms,
                    "repair_attempted": parse.repair_attempted,
                    "repair_succeeded": parse.repair_succeeded,
                }
            )
        write_json(canonical_path, parse.data)
        scores = validate_and_score(parse.data, document["text"], Path(args.schema), require_present_evidence=True)

    return {
        "document_id": document["document_id"],
        "pipeline": "E3",
        "pipeline_id": E3_PIPELINE_ID,
        "provider": args.provider,
        "model": model_name,
        "prompt_path": str(prompt_path),
        "raw_response_path": str(raw_path),
        "canonical_output_path": str(canonical_path) if parse.data is not None else None,
        "parse": {
            "parse_success": parse.parse_success,
            "repair_attempted": parse.repair_attempted,
            "repair_succeeded": parse.repair_succeeded,
            "error": parse.error,
        },
        "scores": scores,
    }


def command_run(args: argparse.Namespace) -> int:
    ids = load_split_ids(Path(args.splits), args.split, args.limit)
    failures = 0
    log_path = Path(args.output_dir) / "event_first_runs.jsonl"
    for document_id in ids:
        document = preprocess_document(document_id, Path(args.exect_root))
        run_root = Path(args.output_dir) / document_id
        payload, e1_record = run_e1(args, document, run_root)
        append_jsonl(log_path, e1_record)
        e1_ok = bool(
            e1_record["parse"]["parse_success"]
            and e1_record["scores"]
            and e1_record["scores"].get("event_constraints_valid")
            and e1_record["scores"].get("quote_validity", {}).get("pass")
        )
        print(f"{'pass' if e1_ok else 'fail'}: E1 {document_id}")
        if not e1_ok:
            failures += 1
            continue

        events = payload["events"] if payload else []
        if "E2" in args.pipelines:
            e2_record = run_e2(args, document, events, run_root)
            append_jsonl(log_path, e2_record)
            scores = e2_record["scores"]
            e2_ok = bool(scores.get("schema_valid") and scores.get("project_constraints_valid") and scores.get("quote_validity", {}).get("pass"))
            print(f"{'pass' if e2_ok else 'fail'}: E2 {document_id}")
            if not e2_ok:
                failures += 1
        if "E3" in args.pipelines:
            e3_record = run_e3(args, document, events, run_root)
            append_jsonl(log_path, e3_record)
            scores = e3_record["scores"] or {}
            e3_ok = bool(
                e3_record.get("parse", {}).get("parse_success")
                and scores.get("schema_valid")
                and scores.get("project_constraints_valid")
                and scores.get("quote_validity", {}).get("pass")
            )
            print(f"{'pass' if e3_ok else 'fail'}: E3 {document_id}")
            if not e3_ok:
                failures += 1
    return 1 if failures else 0


def command_prepare(args: argparse.Namespace) -> int:
    ids = load_split_ids(Path(args.splits), args.split, args.limit)
    for document_id in ids:
        document = preprocess_document(document_id, Path(args.exect_root))
        run_root = Path(args.output_dir) / document_id
        write_text(run_root / "e1_prompt.txt", build_e1_prompt(document))
        print(f"wrote {run_root / 'e1_prompt.txt'}")
        if "E3" in args.pipelines:
            write_text(run_root / "e3_prompt.empty_events.txt", build_e3_prompt(document_id, [], Path(args.schema)))
            print(f"wrote {run_root / 'e3_prompt.empty_events.txt'}")
    return 0


def add_common_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--exect-root", default=str(DEFAULT_EXECT_ROOT))
    parser.add_argument("--splits", default=str(DEFAULT_SPLITS))
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--split", default="development", choices=["development", "validation", "test"])
    parser.add_argument("--limit", type=int, default=2)
    parser.add_argument("--pipelines", nargs="+", default=["E1", "E2"], choices=["E1", "E2", "E3"])
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    run = subparsers.add_parser("run", help="Run event-first extraction and aggregation.")
    add_common_arguments(run)
    run.add_argument("--provider", default="stub", choices=["stub", "openai"])
    run.add_argument("--model", default="gpt-4.1-mini")
    run.set_defaults(func=command_run)

    prepare = subparsers.add_parser("prepare", help="Write event-first prompts without calling a provider.")
    add_common_arguments(prepare)
    prepare.set_defaults(func=command_prepare)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
