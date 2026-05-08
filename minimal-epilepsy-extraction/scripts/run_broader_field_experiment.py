"""M-C2 broader-field feasibility study runner (h008 and h009).

h008: single-prompt Tier 1a (all fields in one call).
h009: two-stage (h004 architecture for seizure frequency + separate broader-only call).
h012: two-stage (h003 full-letter seizure frequency + coverage-oriented broader M-C3 call).
h013: faithful production role pipeline with section/timeline, field extraction,
      verification, and aggregation artifacts.

Records per-row extractions for human adjudication, seizure-frequency metrics against
gold labels, and per-field feasibility metrics.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
import sys
from copy import deepcopy
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from epilepsy_agents.data import iter_records, load_synthetic_subset
from epilepsy_agents.labels import parse_label
from epilepsy_agents.broader_field_schema import tier1a_h010_user_prompt
from epilepsy_agents.llm_pipeline import (
    BroaderFieldContextInjectedPipeline,
    BroaderFieldMediumPipeline,
    BroaderFieldMultiAgentPipeline,
    BroaderFieldSinglePromptPipeline,
    create_provider,
)
from epilepsy_agents.mc3 import score_adjudication_csv
from epilepsy_agents.evaluation_contract import build_row_validity, summarize_validity
from epilepsy_agents.metrics import evaluate_prediction, summarize
from epilepsy_agents.production_pipeline import ProductionMultiAgentPipeline
from epilepsy_agents.schema import EvidenceSpan, Prediction

HARNESS_IDS = {
    "h008": "h008_single_broad_field_llm",
    "h009": "h009_multi_broad_field_llm",
    "h010": "h010_anchored_broad_field_llm",
    "h011": "h011_context_injected_broad_field_llm",
    "h012": "h012_medium_broad_field_llm",
    "h013": "h013_production_multi_agent_llm",
}
MANIFEST_FIELDS = [
    "experiment_id",
    "timestamp_utc",
    "harness_id",
    "pipeline",
    "data_path",
    "data_sha256",
    "row_ok_only",
    "limit",
    "n",
    "exact_label_accuracy",
    "monthly_rate_accuracy_tolerance_15pct",
    "pragmatic_micro_f1",
    "purist_micro_f1",
    "broader_fields_invalid_output_rate",
    "full_contract_invalid_output_rate",
    "mean_implemented_core_field_rate",
    "run_record_path",
    "description",
]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run M-C2 broader-field feasibility study.")
    parser.add_argument("--harness", choices=sorted(HARNESS_IDS), default="h008")
    parser.add_argument("--data", default="data/synthetic_data_subset_1500.json")
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--include-failed-rows", action="store_true")
    parser.add_argument("--experiment-id", default=None)
    parser.add_argument("--description", default="")
    parser.add_argument("--output-dir", default="project_state/runs")
    parser.add_argument("--manifest", default="project_state/experiments/manifest.csv")
    parser.add_argument("--provider", choices=["ollama", "lmstudio", "vllm", "openai", "anthropic"], default="ollama")
    parser.add_argument("--model", default="qwen3.5:4b")
    parser.add_argument("--base-url", default=None)
    parser.add_argument("--timeout-seconds", type=int, default=180)
    parser.add_argument("--max-retries", type=int, default=1)
    parser.add_argument("--num-predict", type=int, default=1024)
    parser.add_argument(
        "--allow-quoted-evidence",
        action="store_true",
        help=(
            "Persist quoted evidence spans in run artifacts for non-canonical datasets. "
            "Canonical synthetic_data_subset_1500.json runs keep evidence by default; "
            "all other data paths are redacted unless this flag is set."
        ),
    )
    parser.add_argument(
        "--adjudication-csv",
        default="docs/adjudication/h008_tier1a_adjudication_25rows_scoring.csv",
        help="Completed human adjudication worksheet to score under locked M-C3 rules when available.",
    )
    return parser


def _build_pipeline(args: argparse.Namespace, provider: Any) -> Any:
    if args.harness == "h009":
        return BroaderFieldMultiAgentPipeline(provider=provider, max_retries=args.max_retries)
    if args.harness == "h010":
        return BroaderFieldSinglePromptPipeline(
            provider=provider,
            max_retries=args.max_retries,
            user_prompt_fn=tier1a_h010_user_prompt,
        )
    if args.harness == "h011":
        return BroaderFieldContextInjectedPipeline(provider=provider, max_retries=args.max_retries)
    if args.harness == "h012":
        return BroaderFieldMediumPipeline(provider=provider, max_retries=args.max_retries)
    if args.harness == "h013":
        return ProductionMultiAgentPipeline(provider=provider, max_retries=args.max_retries)
    return BroaderFieldSinglePromptPipeline(provider=provider, max_retries=args.max_retries)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    harness_id = HARNESS_IDS[args.harness]
    timestamp = datetime.now(timezone.utc).replace(microsecond=0)
    experiment_id = args.experiment_id or _make_id(timestamp, harness_id, args.limit)

    data_path = (ROOT / args.data).resolve() if not Path(args.data).is_absolute() else Path(args.data)
    output_dir = (ROOT / args.output_dir).resolve()
    manifest_path = (ROOT / args.manifest).resolve()
    artifact_policy = _artifact_policy(data_path, args.allow_quoted_evidence)

    provider = create_provider(
        args.provider,
        args.model,
        base_url=args.base_url,
        timeout_seconds=args.timeout_seconds,
        num_predict=args.num_predict,
    )
    pipeline = _build_pipeline(args, provider)
    records = load_synthetic_subset(data_path)

    sf_predictions: list[Prediction] = []
    broader_rows: list[dict[str, Any]] = []

    for record in iter_records(records, args.limit, row_ok_only=not args.include_failed_rows):
        raw_result = pipeline.predict(record.letter)
        result = _normalize_pipeline_result(raw_result)
        sf = result["seizure_frequency"]
        parsed = parse_label(sf["label"])
        sf_prediction = Prediction(
            label=sf["label"],
            evidence=_sf_evidence_spans(sf.get("evidence")),
            confidence=sf["confidence"],
            parsed_monthly_rate=parsed.monthly_rate,
            pragmatic_class=parsed.pragmatic_class,
            purist_class=parsed.purist_class,
            warnings=result.get("warnings", []),
            metadata=result.get("metadata", {}),
        )
        sf_predictions.append(sf_prediction)
        sf_eval = evaluate_prediction(record.source_row_index, record.gold_label, sf_prediction)
        validity = build_row_validity(result)
        broader_rows.append({
            "source_row_index": record.source_row_index,
            "gold_sf_label": record.gold_label,
            "predicted_sf_label": sf["label"],
            "sf_exact_match": sf_eval.exact_match,
            "sf_monthly_rate_match": sf_eval.monthly_rate_match,
            "sf_pragmatic_class": sf_eval.predicted_pragmatic_class,
            "sf_gold_pragmatic_class": sf_eval.gold_pragmatic_class,
            "invalid_output": result.get("invalid_output", False),
            "current_medications": result.get("current_medications", []),
            "seizure_types": result.get("seizure_types", []),
            "investigations": result.get("investigations", []),
            "epilepsy_type": result.get("epilepsy_type", {}),
            "epilepsy_syndrome": result.get("epilepsy_syndrome", {}),
            "validity": validity,
            "production_artifacts": result.get("artifacts", {}),
            "warnings": result.get("warnings", []),
            "latency_ms": _extract_latency(result.get("metadata", {})),
            "call_metadata": _safe_call_metadata(result.get("metadata", {})),
        })

    sf_summary = summarize(
        [evaluate_prediction(r["source_row_index"], r["gold_sf_label"],
                             Prediction(label=r["predicted_sf_label"],
                                        pragmatic_class=r["sf_pragmatic_class"],
                                        purist_class=None,
                                        parsed_monthly_rate=parse_label(r["predicted_sf_label"]).monthly_rate))
         for r in broader_rows]
    )
    feasibility = _compute_feasibility(broader_rows)
    mc3_score = _maybe_score_mc3(args.adjudication_csv)
    n = len(broader_rows)

    run_record = {
        "experiment_id": experiment_id,
        "timestamp_utc": timestamp.isoformat().replace("+00:00", "Z"),
        "harness_id": harness_id,
        "description": args.description,
        "data": {
            "path": _display_path(data_path),
            "sha256": _sha256(data_path),
            "row_ok_only": not args.include_failed_rows,
            "limit": args.limit,
        },
        "code": _git_state(),
        "runtime": {
            "provider": args.provider,
            "model": args.model,
            "num_predict": args.num_predict,
            "timeout_seconds": args.timeout_seconds,
        },
        "artifact_policy": artifact_policy,
        "summary": {
            "n": n,
            "invalid_output_rate": sum(1 for r in broader_rows if r["invalid_output"]) / n if n else 0,
            "validity": summarize_validity(broader_rows),
            "seizure_frequency": sf_summary,
            "feasibility": feasibility,
            "runtime": _runtime_summary(broader_rows),
            "mc3_locked_subset": mc3_score,
        },
        "rows": _artifact_rows(broader_rows, artifact_policy),
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    run_record_path = output_dir / f"{experiment_id}.json"
    run_record_path.write_text(json.dumps(run_record, indent=2), encoding="utf-8")
    _append_manifest(manifest_path, args, harness_id, experiment_id, timestamp, data_path, run_record_path, run_record["summary"])

    print(json.dumps({"experiment_id": experiment_id, "summary": run_record["summary"]}, indent=2))
    print(f"Wrote {_display_path(run_record_path)}")
    return 0


def _compute_feasibility(rows: list[dict[str, Any]]) -> dict[str, Any]:
    n = len(rows)
    if not n:
        return {}

    def field_stats(key: str) -> dict[str, Any]:
        all_items = [item for row in rows for item in row.get(key, [])]
        rows_with_items = sum(1 for row in rows if row.get(key))
        evidence_supported = sum(
            1 for item in all_items if _item_evidence_supported(item)
        )
        return {
            "abstention_rate": round(1 - rows_with_items / n, 3),
            "mean_items_per_row": round(len(all_items) / n, 2),
            "total_items": len(all_items),
            "evidence_support_rate": round(evidence_supported / len(all_items), 3) if all_items else None,
        }

    def classification_stats(key: str) -> dict[str, Any]:
        fields = [row.get(key, {}) for row in rows if isinstance(row.get(key), dict)]
        non_unknown = [
            field
            for field in fields
            if str(field.get("value", "unknown")).strip().lower() not in {"", "unknown"}
        ]
        supported = [
            field
            for field in non_unknown
            if isinstance(field.get("support"), dict) and field["support"].get("supported")
        ]
        return {
            "abstention_rate": round(1 - len(non_unknown) / n, 3),
            "rows_with_value": len(non_unknown),
            "evidence_support_rate": round(len(supported) / len(non_unknown), 3)
            if non_unknown
            else None,
        }

    return {
        "current_medications": field_stats("current_medications"),
        "seizure_types": field_stats("seizure_types"),
        "investigations": field_stats("investigations"),
        "epilepsy_type": classification_stats("epilepsy_type"),
        "epilepsy_syndrome": classification_stats("epilepsy_syndrome"),
    }


def _normalize_pipeline_result(result: dict[str, Any]) -> dict[str, Any]:
    """Return the common broader-run shape for h008-h013 outputs."""
    if "final" not in result:
        return result

    final = result.get("final", {})
    sf = final.get("seizure_frequency", {})
    return {
        "seizure_frequency": {
            "label": sf.get("label", "unknown"),
            "evidence": sf.get("evidence", []),
            "confidence": sf.get("confidence", 0.0),
        },
        "current_medications": final.get("current_medications", []),
        "seizure_types": final.get("seizure_types", []),
        "investigations": final.get("investigations", []),
        "epilepsy_type": final.get("epilepsy_type", {}),
        "epilepsy_syndrome": final.get("epilepsy_syndrome", {}),
        "invalid_output": result.get("invalid_output", False),
        "warnings": result.get("warnings", []),
        "metadata": result.get("metadata", {}),
        "artifacts": result.get("artifacts", {}),
    }


def _sf_evidence_spans(evidence: Any) -> list[EvidenceSpan]:
    if isinstance(evidence, str):
        return [EvidenceSpan(text=evidence)] if evidence.strip() else []
    if isinstance(evidence, list):
        spans = []
        for item in evidence:
            if isinstance(item, dict) and str(item.get("text", "")).strip():
                spans.append(
                    EvidenceSpan(
                        text=str(item["text"]),
                        start=item.get("start"),
                        end=item.get("end"),
                        source=str(item.get("source", "letter")),
                    )
                )
            elif isinstance(item, str) and item.strip():
                spans.append(EvidenceSpan(text=item))
        return spans
    return []


def _item_evidence_supported(item: dict[str, Any]) -> bool:
    support = item.get("support")
    if isinstance(support, dict) and "supported" in support:
        return bool(support["supported"])
    return isinstance(item.get("evidence"), str) and bool(item["evidence"].strip())


def _artifact_policy(data_path: Path, allow_quoted_evidence: bool) -> dict[str, Any]:
    synthetic_path = (ROOT / "data" / "synthetic_data_subset_1500.json").resolve()
    synthetic = data_path.resolve() == synthetic_path
    persist_quoted_evidence = synthetic or allow_quoted_evidence
    return {
        "synthetic_canonical_dataset": synthetic,
        "persist_quoted_evidence": persist_quoted_evidence,
        "redacted": not persist_quoted_evidence,
    }


def _artifact_rows(rows: list[dict[str, Any]], artifact_policy: dict[str, Any]) -> list[dict[str, Any]]:
    if artifact_policy["persist_quoted_evidence"]:
        return rows
    redacted = deepcopy(rows)
    for row in redacted:
        row["sf_evidence_redacted"] = bool(row.get("predicted_sf_label"))
        for key in ("current_medications", "seizure_types", "investigations"):
            for item in row.get(key, []):
                if isinstance(item, dict) and "evidence" in item:
                    item["evidence"] = "[REDACTED]"
        for key in ("epilepsy_type", "epilepsy_syndrome"):
            field = row.get(key)
            if isinstance(field, dict) and field.get("evidence"):
                field["evidence"] = "[REDACTED]"
        if row.get("production_artifacts"):
            row["production_artifacts"] = {"redacted": True}
    return redacted


def _maybe_score_mc3(adjudication_csv: str | None) -> dict[str, Any] | None:
    if not adjudication_csv:
        return None
    path = Path(adjudication_csv)
    if not path.is_absolute():
        path = ROOT / path
    if not path.exists():
        return None
    return score_adjudication_csv(path)


def _extract_latency(metadata: dict[str, Any]) -> float | None:
    """Return total latency for both h008 (flat) and h009 (nested sf_call + broader_call)."""
    if "latency_ms" in metadata:
        return metadata["latency_ms"]
    if "calls" in metadata and isinstance(metadata["calls"], dict):
        metadata = metadata["calls"]
    sf_ms = (metadata.get("sf_call") or {}).get("latency_ms") or 0
    broader_ms = (metadata.get("broader_call") or {}).get("latency_ms") or 0
    classification_ms = (metadata.get("classification_call") or {}).get("latency_ms") or 0
    if sf_ms or broader_ms or classification_ms:
        return sf_ms + broader_ms + classification_ms
    return None


def _safe_call_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    """Keep budget/runtime metadata without raw prompts, completions, or clinical text."""
    allowed = {
        "provider",
        "model",
        "latency_ms",
        "attempt",
        "prompt_tokens",
        "completion_tokens",
        "total_tokens",
        "total_duration",
        "load_duration",
        "prompt_eval_duration",
        "eval_duration",
        "invalid_output",
        "error_type",
        "fallback_used",
        "fallback_reason",
    }
    if not isinstance(metadata, dict):
        return {}
    if "calls" in metadata and isinstance(metadata["calls"], dict):
        metadata = metadata["calls"]
    if "sf_call" in metadata or "broader_call" in metadata or "classification_call" in metadata:
        return {
            key: _safe_call_metadata(value)
            for key, value in metadata.items()
            if key in {"sf_call", "broader_call", "classification_call"} and isinstance(value, dict)
        }
    safe = {key: metadata.get(key) for key in allowed if key in metadata}
    if isinstance(metadata.get("failed_call"), dict):
        safe["failed_call"] = _safe_call_metadata(metadata["failed_call"])
    return safe


def _runtime_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    latencies = [row.get("latency_ms") for row in rows if isinstance(row.get("latency_ms"), (int, float))]
    metadata = [row.get("call_metadata") for row in rows if isinstance(row.get("call_metadata"), dict)]

    def values_for(key: str) -> list[float]:
        values: list[float] = []
        for item in metadata:
            if key in item and isinstance(item[key], (int, float)):
                values.append(float(item[key]))
            else:
                for nested_key in ("sf_call", "broader_call", "classification_call"):
                    nested = item.get(nested_key)
                    if isinstance(nested, dict) and isinstance(nested.get(key), (int, float)):
                        values.append(float(nested[key]))
        return values

    def mean(values: list[float]) -> float | None:
        return round(sum(values) / len(values), 3) if values else None

    total_tokens = values_for("total_tokens")
    prompt_tokens = values_for("prompt_tokens")
    completion_tokens = values_for("completion_tokens")
    return {
        "mean_latency_ms": mean([float(value) for value in latencies]),
        "max_latency_ms": max(latencies) if latencies else None,
        "mean_prompt_tokens": mean(prompt_tokens),
        "mean_completion_tokens": mean(completion_tokens),
        "mean_total_tokens": mean(total_tokens),
        "total_prompt_tokens": int(sum(prompt_tokens)) if prompt_tokens else None,
        "total_completion_tokens": int(sum(completion_tokens)) if completion_tokens else None,
        "total_tokens": int(sum(total_tokens)) if total_tokens else None,
    }


def _make_id(timestamp: datetime, harness_id: str, limit: int) -> str:
    return f"{timestamp.strftime('%Y%m%dT%H%M%SZ')}_{harness_id}_n{limit}"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _display_path(path: Path) -> str:
    resolved = path.resolve()
    if resolved.is_relative_to(ROOT):
        return resolved.relative_to(ROOT).as_posix()
    return str(resolved)


def _git_state() -> dict[str, Any]:
    return {"commit": _run_git("rev-parse", "HEAD"), "dirty": bool(_run_git("status", "--porcelain"))}


def _run_git(*args: str) -> str | None:
    try:
        result = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, check=False, text=True, timeout=5)
    except Exception:
        return None
    return result.stdout.strip() if result.returncode == 0 else None


def _append_manifest(
    manifest_path: Path,
    args: argparse.Namespace,
    harness_id: str,
    experiment_id: str,
    timestamp: datetime,
    data_path: Path,
    run_record_path: Path,
    summary: dict[str, Any],
) -> None:
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    needs_header = not manifest_path.exists() or manifest_path.stat().st_size == 0
    sf = summary.get("seizure_frequency", {})
    validity = summary.get("validity", {})
    row = {
        "experiment_id": experiment_id,
        "timestamp_utc": timestamp.isoformat().replace("+00:00", "Z"),
        "harness_id": harness_id,
        "pipeline": harness_id,
        "data_path": _display_path(data_path),
        "data_sha256": _sha256(data_path),
        "row_ok_only": str(not args.include_failed_rows).lower(),
        "limit": args.limit,
        "n": summary["n"],
        "exact_label_accuracy": sf.get("exact_label_accuracy", ""),
        "monthly_rate_accuracy_tolerance_15pct": sf.get("monthly_rate_accuracy_tolerance_15pct", ""),
        "pragmatic_micro_f1": sf.get("pragmatic", {}).get("micro_f1", ""),
        "purist_micro_f1": sf.get("purist", {}).get("micro_f1", ""),
        "broader_fields_invalid_output_rate": validity.get("broader_fields_invalid_output_rate", ""),
        "full_contract_invalid_output_rate": validity.get("full_contract_invalid_output_rate", ""),
        "mean_implemented_core_field_rate": validity.get("mean_implemented_core_field_rate", ""),
        "run_record_path": _display_path(run_record_path),
        "description": args.description,
    }
    with manifest_path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=MANIFEST_FIELDS)
        if needs_header:
            writer.writeheader()
        writer.writerow(row)


if __name__ == "__main__":
    raise SystemExit(main())
