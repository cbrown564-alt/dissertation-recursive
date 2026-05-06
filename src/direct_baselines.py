#!/usr/bin/env python3
"""Run Milestone 3 direct extraction baselines on a small development subset."""

from __future__ import annotations

import argparse
import json
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from intake import DEFAULT_EXECT_ROOT, DEFAULT_SPLITS, preprocess_document, read_text
from validate_extraction import (
    DEFAULT_SCHEMA,
    ValidationError,
    check_quote_validity,
    iter_evidence,
    validate_project_constraints,
    validate_schema,
)


PROMPT_DIR = Path("prompts/direct_baselines")
DEFAULT_OUTPUT_DIR = Path("runs/direct_baselines")
DEFAULT_ENV_FILE = Path(".env")


BASELINES = {
    "S1": {
        "pipeline_id": "S1_direct_json",
        "format": "json",
        "prompt": PROMPT_DIR / "s1_direct_json.md",
        "require_present_evidence": False,
    },
    "S2": {
        "pipeline_id": "S2_direct_json_evidence",
        "format": "json",
        "prompt": PROMPT_DIR / "s2_direct_json_evidence.md",
        "require_present_evidence": True,
    },
    "S3": {
        "pipeline_id": "S3_yaml_to_json_evidence",
        "format": "yaml_to_json",
        "prompt": PROMPT_DIR / "s3_yaml_evidence.md",
        "require_present_evidence": True,
    },
}


@dataclass
class ParseResult:
    data: Any | None
    parse_success: bool
    repair_attempted: bool
    repair_succeeded: bool
    error: str | None


def write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def append_jsonl(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(value, ensure_ascii=False) + "\n")


def load_split_ids(split_path: Path, split: str, limit: int | None) -> list[str]:
    split_data = json.loads(read_text(split_path))
    ids = split_data[split]
    return ids[:limit] if limit is not None else ids


def compact_schema_text(schema_path: Path) -> str:
    schema = json.loads(read_text(schema_path))
    return json.dumps(schema, indent=2, ensure_ascii=False)


def sentence_table(sentences: list[dict[str, Any]]) -> str:
    rows = []
    for sentence in sentences:
        rows.append(
            f"{sentence['sentence_id']} [{sentence['char_start']}, {sentence['char_end']}]: {sentence['text']}"
        )
    return "\n".join(rows)


def build_prompt(baseline: str, document: dict[str, Any], schema_path: Path) -> str:
    config = BASELINES[baseline]
    instructions = read_text(config["prompt"])
    return "\n\n".join(
        [
            instructions,
            "## Canonical JSON Schema",
            compact_schema_text(schema_path),
            "## Sentence List",
            sentence_table(document["sentences"]),
            "## Source Letter",
            document["text"],
        ]
    )


def empty_scalar(missingness: str = "not_stated", temporality: str = "uncertain") -> dict[str, Any]:
    return {
        "value": None,
        "missingness": missingness,
        "temporality": temporality,
        "evidence": None,
        "evidence_event_ids": [],
        "confidence": None,
    }


def empty_investigation() -> dict[str, Any]:
    return {
        "status": "not_stated",
        "result": "not_stated",
        "missingness": "not_stated",
        "temporality": "uncertain",
        "evidence": None,
        "evidence_event_ids": [],
        "confidence": None,
    }


def stub_extraction(document_id: str, baseline: str, latency_ms: float) -> dict[str, Any]:
    config = BASELINES[baseline]
    seizure_frequency = empty_scalar()
    seizure_frequency["temporal_scope"] = None
    seizure_frequency["seizure_type"] = None
    return {
        "document_id": document_id,
        "pipeline_id": config["pipeline_id"],
        "fields": {
            "current_anti_seizure_medications": [],
            "previous_anti_seizure_medications": [],
            "current_seizure_frequency": seizure_frequency,
            "seizure_types": [],
            "eeg": empty_investigation(),
            "mri": empty_investigation(),
            "epilepsy_diagnosis": empty_scalar(),
        },
        "events": [],
        "metadata": {
            "model": "stub",
            "format": config["format"],
            "latency_ms": latency_ms,
            "input_tokens": 0,
            "output_tokens": 0,
            "repair_attempted": False,
            "repair_succeeded": False,
        },
    }


def strip_code_fence(text: str) -> str:
    stripped = text.strip()
    match = re.fullmatch(r"```(?:json|yaml|yml)?\s*(.*?)\s*```", stripped, flags=re.DOTALL | re.IGNORECASE)
    return match.group(1).strip() if match else stripped


def extract_json_object(text: str) -> str:
    stripped = strip_code_fence(text)
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return stripped
    return stripped[start : end + 1]


def repair_json_text(text: str) -> str:
    repaired = extract_json_object(text)
    repaired = re.sub(r",(\s*[}\]])", r"\1", repaired)
    return repaired


def parse_json_response(text: str) -> ParseResult:
    raw = extract_json_object(text)
    try:
        return ParseResult(json.loads(raw), True, False, False, None)
    except json.JSONDecodeError as first_error:
        repaired = repair_json_text(text)
        try:
            return ParseResult(json.loads(repaired), True, True, True, None)
        except json.JSONDecodeError as second_error:
            return ParseResult(None, False, True, False, f"{first_error}; repair failed: {second_error}")


def parse_yaml_response(text: str) -> ParseResult:
    try:
        import yaml
    except ImportError as exc:
        return ParseResult(None, False, False, False, f"PyYAML is not installed: {exc}")

    raw = strip_code_fence(text)
    try:
        return ParseResult(yaml.safe_load(raw), True, False, False, None)
    except yaml.YAMLError as first_error:
        repaired = raw.replace("\t", "  ")
        try:
            return ParseResult(yaml.safe_load(repaired), True, True, True, None)
        except yaml.YAMLError as second_error:
            return ParseResult(None, False, True, False, f"{first_error}; repair failed: {second_error}")


def parse_model_response(text: str, baseline: str) -> ParseResult:
    if BASELINES[baseline]["format"] == "yaml_to_json":
        return parse_yaml_response(text)
    return parse_json_response(text)


def load_dotenv(path: Path = DEFAULT_ENV_FILE) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("'\"")
        if key and key not in os.environ:
            os.environ[key] = value


def render_stub_response(document_id: str, baseline: str, latency_ms: float) -> str:
    data = stub_extraction(document_id, baseline, latency_ms)
    if BASELINES[baseline]["format"] == "yaml_to_json":
        lines = [
            f"document_id: {data['document_id']}",
            f"pipeline_id: {data['pipeline_id']}",
            "fields:",
            "  current_anti_seizure_medications: []",
            "  previous_anti_seizure_medications: []",
            "  current_seizure_frequency:",
            "    value: null",
            "    missingness: not_stated",
            "    temporality: uncertain",
            "    temporal_scope: null",
            "    seizure_type: null",
            "    evidence: null",
            "    evidence_event_ids: []",
            "    confidence: null",
            "  seizure_types: []",
            "  eeg: &not_stated_investigation",
            "    status: not_stated",
            "    result: not_stated",
            "    missingness: not_stated",
            "    temporality: uncertain",
            "    evidence: null",
            "    evidence_event_ids: []",
            "    confidence: null",
            "  mri: *not_stated_investigation",
            "  epilepsy_diagnosis:",
            "    value: null",
            "    missingness: not_stated",
            "    temporality: uncertain",
            "    evidence: null",
            "    evidence_event_ids: []",
            "    confidence: null",
            "events: []",
            "metadata:",
            "  model: stub",
            f"  format: {data['metadata']['format']}",
            f"  latency_ms: {latency_ms}",
            "  input_tokens: 0",
            "  output_tokens: 0",
            "  repair_attempted: false",
            "  repair_succeeded: false",
        ]
        return "\n".join(lines) + "\n"
    return json.dumps(data, indent=2, ensure_ascii=False)


def call_openai(prompt: str, model: str) -> str:
    load_dotenv()
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError("openai is not installed; run `python3 -m pip install -r requirements.txt`") from exc
    if not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is not set")
    client = OpenAI()
    response = client.responses.create(model=model, input=prompt)
    return response.output_text


def get_model_response(args: argparse.Namespace, prompt: str, document_id: str, baseline: str) -> tuple[str, float, str]:
    started = time.perf_counter()
    if args.provider == "stub":
        latency_ms = (time.perf_counter() - started) * 1000
        return render_stub_response(document_id, baseline, latency_ms), latency_ms, "stub"
    if args.provider == "openai":
        response = call_openai(prompt, args.model)
        latency_ms = (time.perf_counter() - started) * 1000
        return response, latency_ms, args.model
    raise ValueError(f"unsupported provider: {args.provider}")


def evidence_presence_score(data: Any) -> dict[str, Any]:
    missing = []
    total_present = 0

    def visit(value: Any, path: str) -> None:
        nonlocal total_present
        if isinstance(value, dict):
            if value.get("missingness") == "present":
                total_present += 1
                evidence = value.get("evidence")
                if not evidence:
                    missing.append(path)
            for key, child in value.items():
                visit(child, f"{path}.{key}")
        elif isinstance(value, list):
            for index, child in enumerate(value):
                visit(child, f"{path}[{index}]")

    if isinstance(data, dict):
        visit(data.get("fields", {}), "$.fields")
    return {
        "present_field_count": total_present,
        "missing_evidence_count": len(missing),
        "missing_evidence_paths": missing,
        "pass": len(missing) == 0,
    }


def validate_and_score(
    data: Any,
    source_text: str,
    schema_path: Path,
    require_present_evidence: bool,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "schema_valid": False,
        "project_constraints_valid": False,
        "quote_presence": None,
        "quote_validity": None,
        "semantic_support": {"status": "not_scored_in_milestone_3"},
        "temporal_support": {"status": "not_scored_in_milestone_3"},
        "field_correctness": {"status": "not_scored_in_milestone_3"},
        "validation_errors": [],
    }
    try:
        validate_schema(data, schema_path)
        result["schema_valid"] = True
    except ValidationError as exc:
        result["validation_errors"].append(str(exc))
        return result

    result["quote_presence"] = evidence_presence_score(data)
    try:
        validate_project_constraints(data, require_present_evidence=require_present_evidence)
        result["project_constraints_valid"] = True
    except ValidationError as exc:
        result["validation_errors"].append(str(exc))

    quote_total, quote_failures = check_quote_validity(data, source_text)
    result["quote_validity"] = {
        "quote_count": quote_total,
        "valid_quote_count": quote_total - len(quote_failures),
        "invalid_quote_count": len(quote_failures),
        "invalid_quote_paths": quote_failures,
        "pass": len(quote_failures) == 0,
    }
    result["evidence_quote_count"] = len(iter_evidence(data))
    return result


def enrich_metadata(data: Any, baseline: str, model_name: str, latency_ms: float, parse: ParseResult) -> None:
    if not isinstance(data, dict):
        return
    data.setdefault("metadata", {})
    data["metadata"].update(
        {
            "model": model_name,
            "format": BASELINES[baseline]["format"],
            "latency_ms": latency_ms,
            "repair_attempted": parse.repair_attempted,
            "repair_succeeded": parse.repair_succeeded,
        }
    )


def parse_log(parse: ParseResult) -> dict[str, Any]:
    return {
        "parse_success": parse.parse_success,
        "repair_attempted": parse.repair_attempted,
        "repair_succeeded": parse.repair_succeeded,
        "error": parse.error,
    }


def run_one(args: argparse.Namespace, document_id: str, baseline: str) -> dict[str, Any]:
    config = BASELINES[baseline]
    document = preprocess_document(document_id, Path(args.exect_root))
    prompt = build_prompt(baseline, document, Path(args.schema))

    run_root = Path(args.output_dir) / baseline / document_id
    prompt_path = run_root / "prompt.txt"
    raw_path = run_root / ("raw.yaml" if config["format"] == "yaml_to_json" else "raw.json")
    extraction_path = run_root / "canonical.json"

    write_text(prompt_path, prompt)
    raw_response, latency_ms, model_name = get_model_response(args, prompt, document_id, baseline)
    write_text(raw_path, raw_response)

    parse = parse_model_response(raw_response, baseline)
    scores: dict[str, Any] | None = None
    if parse.data is not None:
        enrich_metadata(parse.data, baseline, model_name, latency_ms, parse)
        write_json(extraction_path, parse.data)
        scores = validate_and_score(
            parse.data,
            document["text"],
            Path(args.schema),
            require_present_evidence=config["require_present_evidence"],
        )

    log_record = {
        "document_id": document_id,
        "baseline": baseline,
        "pipeline_id": config["pipeline_id"],
        "provider": args.provider,
        "model": model_name,
        "prompt_path": str(prompt_path),
        "raw_response_path": str(raw_path),
        "canonical_output_path": str(extraction_path) if parse.data is not None else None,
        "parse": parse_log(parse),
        "scores": scores,
    }
    append_jsonl(Path(args.output_dir) / "baseline_runs.jsonl", log_record)
    return log_record


def command_run(args: argparse.Namespace) -> int:
    ids = load_split_ids(Path(args.splits), args.split, args.limit)
    failures = 0
    for document_id in ids:
        for baseline in args.baselines:
            record = run_one(args, document_id, baseline)
            scores = record["scores"] or {}
            ok = record["parse"]["parse_success"] and scores.get("schema_valid") and scores.get("project_constraints_valid")
            status = "pass" if ok else "fail"
            print(f"{status}: {baseline} {document_id}")
            if not ok:
                failures += 1
    return 1 if failures else 0


def command_prepare(args: argparse.Namespace) -> int:
    ids = load_split_ids(Path(args.splits), args.split, args.limit)
    for document_id in ids:
        document = preprocess_document(document_id, Path(args.exect_root))
        for baseline in args.baselines:
            prompt = build_prompt(baseline, document, Path(args.schema))
            prompt_path = Path(args.output_dir) / baseline / document_id / "prompt.txt"
            write_text(prompt_path, prompt)
            print(f"wrote {prompt_path}")
    return 0


def add_common_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--exect-root", default=str(DEFAULT_EXECT_ROOT))
    parser.add_argument("--splits", default=str(DEFAULT_SPLITS))
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--split", default="development", choices=["development", "validation", "test"])
    parser.add_argument("--limit", type=int, default=2)
    parser.add_argument("--baselines", nargs="+", default=["S1", "S2", "S3"], choices=sorted(BASELINES))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    run = subparsers.add_parser("run", help="Run direct baselines and validate/log outputs.")
    add_common_arguments(run)
    run.add_argument("--provider", default="stub", choices=["stub", "openai"])
    run.add_argument("--model", default="gpt-4.1-mini")
    run.set_defaults(func=command_run)

    prepare = subparsers.add_parser("prepare", help="Write model prompts without calling a provider.")
    add_common_arguments(prepare)
    prepare.set_defaults(func=command_prepare)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
