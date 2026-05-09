from __future__ import annotations

import csv
import json
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

from epilepsy_extraction.models.registry import ModelRegistryEntry, load_registry
from epilepsy_extraction.schemas.contracts import CORE_FIELD_FAMILIES, FieldFamily


TABLE_ORDER: tuple[str, ...] = (
    "architecture_harness_coverage",
    "baseline_comparability",
    "model_registry",
    "budget_complexity",
    "harness_complexity",
    "parse_validity",
    "field_level_correctness",
    "evidence_support",
    "architecture_ablation",
    "model_family",
    "seizure_frequency_anchor",
    "self_consistency_cost",
)

TABLE_HEADERS: dict[str, list[str]] = {
    "architecture_harness_coverage": [
        "run_id",
        "harness",
        "architecture_family",
        "status",
        "dataset_id",
        "dataset_n",
        "field_family",
        "coverage_status",
        "partial_contract",
    ],
    "baseline_comparability": [
        "run_id",
        "harness",
        "external_baseline",
        "mapping_version",
        "field_family",
        "coverage_status",
        "evidence_available",
        "comparability_notes",
    ],
    "model_registry": [
        "model_registry_entry",
        "model_id",
        "display_name",
        "provider",
        "family",
        "tier",
        "context_window",
        "frozen_at",
        "used_in_runs",
        "notes",
    ],
    "budget_complexity": [
        "run_id",
        "harness",
        "architecture_family",
        "provider",
        "model",
        "temperature",
        "prompt_version",
        "schema_version",
        "mapping_version",
        "dataset_n",
        "llm_calls_per_row",
        "mean_input_tokens",
        "mean_output_tokens",
        "mean_total_tokens",
        "latency_ms",
        "estimated_cost_usd",
        "modules_invoked",
        "intermediate_artifacts",
        "external_tools",
    ],
    "harness_complexity": [
        "run_id",
        "harness",
        "architecture_family",
        "manifest_id",
        "manifest_hash",
        "dataset_n",
        "llm_calls_per_row",
        "modules_invoked",
        "workflow_units",
        "provider_calls",
        "event_count",
        "parse_repair_attempts",
        "verifier_passes",
        "escalation_decisions",
        "intermediate_artifacts",
        "raw_artifact_paths",
        "complexity_status",
    ],
    "parse_validity": [
        "run_id",
        "harness",
        "architecture_family",
        "component",
        "valid",
        "invalid",
        "total",
        "valid_rate",
        "invalid_rate",
    ],
    "field_level_correctness": [
        "run_id",
        "harness",
        "field_family",
        "n",
        "exact_label_accuracy",
        "monthly_rate_accuracy_tolerance_15pct",
        "pragmatic_macro_f1",
        "pragmatic_weighted_f1",
        "purist_macro_f1",
        "purist_weighted_f1",
        "adjudication_status",
    ],
    "evidence_support": [
        "run_id",
        "harness",
        "architecture_family",
        "total_citations",
        "supported_citations",
        "unsupported_citations",
        "evidence_supported_rate",
        "evidence_status",
    ],
    "architecture_ablation": [
        "dataset_id",
        "model_registry_entry",
        "baseline_run_id",
        "comparison_run_id",
        "baseline_harness",
        "comparison_harness",
        "matched_rows",
        "exact_label_accuracy_delta",
        "monthly_rate_accuracy_delta",
        "cost_delta_usd",
        "total_token_delta",
        "parse_validity_delta",
    ],
    "model_family": [
        "run_id",
        "harness",
        "architecture_family",
        "model_registry_entry",
        "model_id",
        "provider",
        "family",
        "tier",
        "dataset_n",
        "exact_label_accuracy",
        "evidence_supported_rate",
        "parse_valid_rate",
        "estimated_cost_usd",
        "latency_ms",
    ],
    "seizure_frequency_anchor": [
        "run_id",
        "harness",
        "architecture_family",
        "model",
        "dataset_n",
        "exact_label_accuracy",
        "monthly_rate_accuracy_tolerance_15pct",
        "pragmatic_macro_f1",
        "purist_macro_f1",
        "warnings",
    ],
    "self_consistency_cost": [
        "run_id",
        "harness",
        "base_harness",
        "self_consistency_samples",
        "dataset_n",
        "llm_calls_per_row",
        "mean_total_tokens",
        "estimated_cost_usd",
        "exact_label_accuracy",
        "monthly_rate_accuracy_tolerance_15pct",
    ],
}


def load_run_records(paths: Iterable[str | Path]) -> list[dict[str, Any]]:
    return [json.loads(Path(path).read_text(encoding="utf-8")) for path in paths]


def build_result_tables(
    run_records: Sequence[Mapping[str, Any]],
    model_registry_path: str | Path | None = None,
) -> dict[str, list[dict[str, Any]]]:
    runs = [dict(record) for record in run_records]
    registry_entries = load_registry(model_registry_path) if model_registry_path else []
    registry_by_id = {entry.model_id: entry for entry in registry_entries}

    return {
        "architecture_harness_coverage": _architecture_harness_coverage(runs),
        "baseline_comparability": _baseline_comparability(runs),
        "model_registry": _model_registry_table(runs, registry_entries),
        "budget_complexity": _budget_complexity(runs),
        "harness_complexity": _harness_complexity(runs),
        "parse_validity": _parse_validity(runs),
        "field_level_correctness": _field_level_correctness(runs),
        "evidence_support": _evidence_support(runs),
        "architecture_ablation": _architecture_ablation(runs),
        "model_family": _model_family(runs, registry_by_id),
        "seizure_frequency_anchor": _seizure_frequency_anchor(runs),
        "self_consistency_cost": _self_consistency_cost(runs),
    }


def write_result_tables(tables: Mapping[str, Sequence[Mapping[str, Any]]], output_dir: str | Path) -> list[Path]:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for table_name in TABLE_ORDER:
        rows = list(tables.get(table_name, []))
        json_path = output_path / f"{table_name}.json"
        csv_path = output_path / f"{table_name}.csv"
        json_path.write_text(json.dumps(rows, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        _write_csv(csv_path, TABLE_HEADERS[table_name], rows)
        written.extend([json_path, csv_path])
    return written


def _architecture_harness_coverage(runs: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for run in runs:
        coverage = _field_coverage(run)
        partial_contract = any(
            status != "implemented"
            for field, status in coverage.items()
            if field in {family.value for family in CORE_FIELD_FAMILIES}
        )
        for field in _ordered_field_families(coverage):
            rows.append(
                _select(
                    {
                        "run_id": run.get("run_id", ""),
                        "harness": run.get("harness", ""),
                        "architecture_family": run.get("architecture_family", ""),
                        "status": run.get("status", ""),
                        "dataset_id": _dataset(run).get("dataset_id", ""),
                        "dataset_n": _dataset_n(run),
                        "field_family": field,
                        "coverage_status": coverage.get(field, ""),
                        "partial_contract": partial_contract,
                    },
                    TABLE_HEADERS["architecture_harness_coverage"],
                )
            )
    return rows


def _baseline_comparability(runs: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for run in runs:
        if not (
            run.get("architecture_family") == "clinical_nlp_baseline"
            or run.get("external_baseline")
            or run.get("mapping_version")
        ):
            continue
        coverage = _field_coverage(run)
        for field in _ordered_field_families(coverage):
            status = coverage.get(field, "")
            evidence_available = _baseline_evidence_available(status, run)
            rows.append(
                _select(
                    {
                        "run_id": run.get("run_id", ""),
                        "harness": run.get("harness", ""),
                        "external_baseline": bool(run.get("external_baseline", False)),
                        "mapping_version": run.get("mapping_version", ""),
                        "field_family": field,
                        "coverage_status": status,
                        "evidence_available": evidence_available,
                        "comparability_notes": _comparability_notes(status, evidence_available),
                    },
                    TABLE_HEADERS["baseline_comparability"],
                )
            )
    return rows


def _model_registry_table(
    runs: Sequence[Mapping[str, Any]],
    registry_entries: Sequence[ModelRegistryEntry],
) -> list[dict[str, Any]]:
    used: dict[str, list[str]] = {}
    for run in runs:
        entry_id = run.get("model_registry_entry") or run.get("model")
        if entry_id:
            used.setdefault(str(entry_id), []).append(str(run.get("run_id", "")))

    rows = [
        _select(
            {
                "model_registry_entry": entry.model_id,
                **entry.to_dict(),
                "used_in_runs": ";".join(sorted(used.get(entry.model_id, []))),
            },
            TABLE_HEADERS["model_registry"],
        )
        for entry in registry_entries
    ]
    known_ids = {entry.model_id for entry in registry_entries}
    for entry_id, run_ids in sorted(used.items()):
        if entry_id in known_ids or entry_id == "none":
            continue
        rows.append(
            _select(
                {
                    "model_registry_entry": entry_id,
                    "model_id": entry_id,
                    "used_in_runs": ";".join(sorted(run_ids)),
                    "notes": "not found in supplied registry",
                },
                TABLE_HEADERS["model_registry"],
            )
        )
    return rows


def _budget_complexity(runs: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for run in runs:
        budget = _budget(run)
        complexity = run.get("complexity") if isinstance(run.get("complexity"), Mapping) else {}
        modules = complexity.get("modules", []) if isinstance(complexity, Mapping) else []
        external_tools = complexity.get("external_tools", []) if isinstance(complexity, Mapping) else []
        rows.append(
            _select(
                {
                    "run_id": run.get("run_id", ""),
                    "harness": run.get("harness", ""),
                    "architecture_family": run.get("architecture_family", ""),
                    "provider": run.get("provider", ""),
                    "model": run.get("model", ""),
                    "temperature": run.get("temperature", ""),
                    "prompt_version": run.get("prompt_version", ""),
                    "schema_version": run.get("schema_version", ""),
                    "mapping_version": run.get("mapping_version", ""),
                    "dataset_n": _dataset_n(run),
                    "llm_calls_per_row": budget.get("llm_calls_per_row", 0),
                    "mean_input_tokens": _per_row(budget.get("input_tokens", 0), run),
                    "mean_output_tokens": _per_row(budget.get("output_tokens", 0), run),
                    "mean_total_tokens": _per_row(budget.get("total_tokens", 0), run),
                    "latency_ms": budget.get("latency_ms", 0),
                    "estimated_cost_usd": budget.get("estimated_cost_usd", 0.0),
                    "modules_invoked": len(modules) if isinstance(modules, list) else complexity.get("modules_invoked", ""),
                    "intermediate_artifacts": len(run.get("artifact_paths", {}) or {}),
                    "external_tools": ";".join(external_tools) if isinstance(external_tools, list) else external_tools,
                },
                TABLE_HEADERS["budget_complexity"],
            )
        )
    return rows


def _harness_complexity(runs: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for run in runs:
        complexity = run.get("complexity") if isinstance(run.get("complexity"), Mapping) else {}
        budget = _budget(run)
        manifest = _manifest(run)
        event_summary = _event_summary(run)
        modules = _count_from(complexity, "modules", fallback_key="modules_invoked")
        workflow_units = _count_from(complexity, "workflow_units", fallback_key="workflow_units_invoked")
        provider_calls = event_summary.get("provider_calls", "")
        if provider_calls == "":
            provider_calls = _event_type_count(run, "provider_call_started")
        event_count = event_summary.get("event_count", "")
        if event_count == "":
            event_count = len(_event_log(run))
        parse_repairs = event_summary.get("parse_repair_attempts", "")
        if parse_repairs == "":
            parse_repairs = _event_type_count(run, "parse_repaired")
        verifier_passes = event_summary.get("verifier_passes", "")
        if verifier_passes == "":
            verifier_passes = _event_type_count(run, "verification_completed")
        escalation_decisions = event_summary.get("escalation_decisions", "")
        if escalation_decisions == "":
            escalation_decisions = _event_type_count(run, "escalation_decision")
        raw_artifacts = run.get("raw_artifacts") or run.get("raw_artifact_paths") or {}
        rows.append(
            _select(
                {
                    "run_id": run.get("run_id", ""),
                    "harness": run.get("harness", ""),
                    "architecture_family": run.get("architecture_family", ""),
                    "manifest_id": manifest.get("id", ""),
                    "manifest_hash": manifest.get("hash", ""),
                    "dataset_n": _dataset_n(run),
                    "llm_calls_per_row": budget.get("llm_calls_per_row", 0),
                    "modules_invoked": modules,
                    "workflow_units": workflow_units,
                    "provider_calls": provider_calls,
                    "event_count": event_count,
                    "parse_repair_attempts": parse_repairs,
                    "verifier_passes": verifier_passes,
                    "escalation_decisions": escalation_decisions,
                    "intermediate_artifacts": len(run.get("artifact_paths", {}) or {}),
                    "raw_artifact_paths": len(raw_artifacts)
                    if isinstance(raw_artifacts, Mapping) or isinstance(raw_artifacts, list)
                    else "",
                    "complexity_status": _complexity_status(run),
                },
                TABLE_HEADERS["harness_complexity"],
            )
        )
    return rows


def _parse_validity(runs: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for run in runs:
        validity = run.get("parse_validity", {})
        if not isinstance(validity, Mapping):
            continue
        for component, stats in sorted(validity.items()):
            if not isinstance(stats, Mapping):
                continue
            total = stats.get("total", 0) or 0
            valid = stats.get("valid", 0) or 0
            invalid = stats.get("invalid", 0) or 0
            valid_rate = stats.get("valid_rate", valid / total if total else "")
            rows.append(
                _select(
                    {
                        "run_id": run.get("run_id", ""),
                        "harness": run.get("harness", ""),
                        "architecture_family": run.get("architecture_family", ""),
                        "component": component,
                        "valid": valid,
                        "invalid": invalid,
                        "total": total,
                        "valid_rate": valid_rate,
                        "invalid_rate": 1 - valid_rate if isinstance(valid_rate, int | float) else "",
                    },
                    TABLE_HEADERS["parse_validity"],
                )
            )
    return rows


_CORE_FIELD_FAMILIES = (
    "seizure_frequency",
    "current_medications",
    "investigations",
    "seizure_classification",
    "epilepsy_classification",
)


def _field_level_correctness(runs: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for run in runs:
        if run.get("status") == "smoke":
            continue
        metrics = _metrics(run)
        # One row per field family so the cockpit heatmap has all columns
        for fam in _CORE_FIELD_FAMILIES:
            fam_metrics = metrics if fam == "seizure_frequency" else {}
            rows.append(
                _select(
                    {
                        "run_id": run.get("run_id", ""),
                        "harness": run.get("harness", ""),
                        "field_family": fam,
                        "n": fam_metrics.get("n", _dataset_n(run)),
                        "exact_label_accuracy": fam_metrics.get("exact_label_accuracy", ""),
                        "monthly_rate_accuracy_tolerance_15pct": fam_metrics.get(
                            "monthly_rate_accuracy_tolerance_15pct", ""
                        ),
                        "pragmatic_macro_f1": _nested(fam_metrics, "pragmatic", "macro_f1"),
                        "pragmatic_weighted_f1": _nested(fam_metrics, "pragmatic", "weighted_f1"),
                        "purist_macro_f1": _nested(fam_metrics, "purist", "macro_f1"),
                        "purist_weighted_f1": _nested(fam_metrics, "purist", "weighted_f1"),
                        "adjudication_status": "not_adjudicated",
                    },
                    TABLE_HEADERS["field_level_correctness"],
                )
            )
    return rows


def _evidence_support(runs: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for run in runs:
        support = _metrics(run).get("evidence_support")
        if isinstance(support, Mapping):
            values = {
                "total_citations": support.get("total_citations", 0),
                "supported_citations": support.get("supported_citations", 0),
                "unsupported_citations": support.get("unsupported_citations", 0),
                "evidence_supported_rate": support.get("evidence_supported_rate", ""),
                "evidence_status": "reported",
            }
        else:
            values = {
                "total_citations": "",
                "supported_citations": "",
                "unsupported_citations": "",
                "evidence_supported_rate": "",
                "evidence_status": "not_reported",
            }
        rows.append(
            _select(
                {
                    "run_id": run.get("run_id", ""),
                    "harness": run.get("harness", ""),
                    "architecture_family": run.get("architecture_family", ""),
                    **values,
                },
                TABLE_HEADERS["evidence_support"],
            )
        )
    return rows


def _architecture_ablation(runs: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    sorted_runs = sorted(runs, key=lambda run: str(run.get("run_id", "")))
    for index, baseline in enumerate(sorted_runs):
        for comparison in sorted_runs[index + 1 :]:
            if _dataset(baseline).get("data_hash") != _dataset(comparison).get("data_hash"):
                continue
            if _row_ids(baseline) != _row_ids(comparison):
                continue
            if _model_key(baseline) != _model_key(comparison):
                continue
            rows.append(
                _select(
                    {
                        "dataset_id": _dataset(baseline).get("dataset_id", ""),
                        "model_registry_entry": _model_key(baseline),
                        "baseline_run_id": baseline.get("run_id", ""),
                        "comparison_run_id": comparison.get("run_id", ""),
                        "baseline_harness": baseline.get("harness", ""),
                        "comparison_harness": comparison.get("harness", ""),
                        "matched_rows": _dataset_n(baseline),
                        "exact_label_accuracy_delta": _metric_delta(
                            baseline, comparison, "exact_label_accuracy"
                        ),
                        "monthly_rate_accuracy_delta": _metric_delta(
                            baseline, comparison, "monthly_rate_accuracy_tolerance_15pct"
                        ),
                        "cost_delta_usd": (_budget(comparison).get("estimated_cost_usd", 0.0) or 0.0)
                        - (_budget(baseline).get("estimated_cost_usd", 0.0) or 0.0),
                        "total_token_delta": (_budget(comparison).get("total_tokens", 0) or 0)
                        - (_budget(baseline).get("total_tokens", 0) or 0),
                        "parse_validity_delta": _parse_valid_rate(comparison) - _parse_valid_rate(baseline),
                    },
                    TABLE_HEADERS["architecture_ablation"],
                )
            )
    return rows


def _model_family(
    runs: Sequence[Mapping[str, Any]],
    registry_by_id: Mapping[str, ModelRegistryEntry],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for run in runs:
        entry_id = str(run.get("model_registry_entry") or run.get("model") or "")
        entry = registry_by_id.get(entry_id)
        metrics = _metrics(run)
        evidence = metrics.get("evidence_support", {})
        rows.append(
            _select(
                {
                    "run_id": run.get("run_id", ""),
                    "harness": run.get("harness", ""),
                    "architecture_family": run.get("architecture_family", ""),
                    "model_registry_entry": run.get("model_registry_entry", ""),
                    "model_id": entry.model_id if entry else run.get("model", ""),
                    "provider": entry.provider if entry else run.get("provider", ""),
                    "family": entry.family if entry else "",
                    "tier": entry.tier if entry else "",
                    "dataset_n": _dataset_n(run),
                    "exact_label_accuracy": metrics.get("exact_label_accuracy", ""),
                    "evidence_supported_rate": evidence.get("evidence_supported_rate", "")
                    if isinstance(evidence, Mapping)
                    else "",
                    "parse_valid_rate": _parse_valid_rate(run),
                    "estimated_cost_usd": _budget(run).get("estimated_cost_usd", 0.0),
                    "latency_ms": _budget(run).get("latency_ms", 0),
                },
                TABLE_HEADERS["model_family"],
            )
        )
    return rows


def _seizure_frequency_anchor(runs: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for run in runs:
        if "anchor" not in str(run.get("harness", "")):
            continue
        metrics = _metrics(run)
        rows.append(
            _select(
                {
                    "run_id": run.get("run_id", ""),
                    "harness": run.get("harness", ""),
                    "architecture_family": run.get("architecture_family", ""),
                    "model": run.get("model", ""),
                    "dataset_n": _dataset_n(run),
                    "exact_label_accuracy": metrics.get("exact_label_accuracy", ""),
                    "monthly_rate_accuracy_tolerance_15pct": metrics.get(
                        "monthly_rate_accuracy_tolerance_15pct", ""
                    ),
                    "pragmatic_macro_f1": _nested(metrics, "pragmatic", "macro_f1"),
                    "purist_macro_f1": _nested(metrics, "purist", "macro_f1"),
                    "warnings": ";".join(run.get("warnings", []) or []),
                },
                TABLE_HEADERS["seizure_frequency_anchor"],
            )
        )
    return rows


def _self_consistency_cost(runs: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for run in runs:
        harness = str(run.get("harness", ""))
        samples = _self_consistency_samples(harness)
        if samples is None:
            continue
        budget = _budget(run)
        metrics = _metrics(run)
        rows.append(
            _select(
                {
                    "run_id": run.get("run_id", ""),
                    "harness": harness,
                    "base_harness": harness.rsplit("_sc", 1)[0],
                    "self_consistency_samples": samples,
                    "dataset_n": _dataset_n(run),
                    "llm_calls_per_row": budget.get("llm_calls_per_row", 0),
                    "mean_total_tokens": _per_row(budget.get("total_tokens", 0), run),
                    "estimated_cost_usd": budget.get("estimated_cost_usd", 0.0),
                    "exact_label_accuracy": metrics.get("exact_label_accuracy", ""),
                    "monthly_rate_accuracy_tolerance_15pct": metrics.get(
                        "monthly_rate_accuracy_tolerance_15pct", ""
                    ),
                },
                TABLE_HEADERS["self_consistency_cost"],
            )
        )
    return rows


def _write_csv(path: Path, headers: Sequence[str], rows: Sequence[Mapping[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(headers), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: _csv_value(row.get(key, "")) for key in headers})


def _field_coverage(run: Mapping[str, Any]) -> dict[str, str]:
    coverage = run.get("field_coverage", {})
    return dict(coverage) if isinstance(coverage, Mapping) else {}


def _ordered_field_families(coverage: Mapping[str, str]) -> list[str]:
    known = [field.value for field in FieldFamily if field.value in coverage]
    extra = sorted(field for field in coverage if field not in known)
    return known + extra


def _dataset(run: Mapping[str, Any]) -> Mapping[str, Any]:
    dataset = run.get("dataset", {})
    return dataset if isinstance(dataset, Mapping) else {}


def _dataset_n(run: Mapping[str, Any]) -> int:
    dataset = _dataset(run)
    n = dataset.get("n")
    return int(n) if isinstance(n, int | float | str) and str(n).isdigit() else len(_row_ids(run))


def _row_ids(run: Mapping[str, Any]) -> tuple[str, ...]:
    row_ids = _dataset(run).get("row_ids", [])
    return tuple(str(row_id) for row_id in row_ids) if isinstance(row_ids, list) else ()


def _budget(run: Mapping[str, Any]) -> Mapping[str, Any]:
    budget = run.get("budget", {})
    return budget if isinstance(budget, Mapping) else {}


def _metrics(run: Mapping[str, Any]) -> Mapping[str, Any]:
    metrics = run.get("metrics", {})
    return metrics if isinstance(metrics, Mapping) else {}


def _manifest(run: Mapping[str, Any]) -> Mapping[str, Any]:
    manifest = run.get("harness_manifest") or run.get("manifest") or {}
    if isinstance(manifest, Mapping):
        manifest_id = manifest.get("id") or manifest.get("manifest_id") or run.get("manifest_id", "")
        manifest_hash = manifest.get("hash") or manifest.get("manifest_hash") or run.get("manifest_hash", "")
        return {"id": manifest_id, "hash": manifest_hash}
    return {
        "id": run.get("manifest_id", ""),
        "hash": run.get("manifest_hash", ""),
    }


def _event_log(run: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    events = run.get("harness_events") or run.get("event_log") or []
    if not isinstance(events, list):
        return []
    return [event for event in events if isinstance(event, Mapping)]


def _event_summary(run: Mapping[str, Any]) -> Mapping[str, Any]:
    summary = run.get("event_summary") or run.get("harness_event_summary") or {}
    return summary if isinstance(summary, Mapping) else {}


def _event_type_count(run: Mapping[str, Any], event_type: str) -> int:
    return sum(1 for event in _event_log(run) if event.get("event_type") == event_type or event.get("type") == event_type)


def _count_from(data: Mapping[str, Any], key: str, fallback_key: str) -> int | str:
    value = data.get(key)
    if isinstance(value, list) or isinstance(value, tuple) or isinstance(value, set):
        return len(value)
    if isinstance(value, int | float):
        return int(value)
    fallback = data.get(fallback_key)
    if isinstance(fallback, int | float):
        return int(fallback)
    return ""


def _complexity_status(run: Mapping[str, Any]) -> str:
    has_manifest = bool(_manifest(run).get("id"))
    has_events = bool(_event_summary(run) or _event_log(run))
    has_complexity = isinstance(run.get("complexity"), Mapping) and bool(run.get("complexity"))
    if has_manifest and has_events:
        return "harness_native"
    if has_manifest or has_events or has_complexity:
        return "partial"
    return "legacy_or_not_reported"


def _per_row(value: Any, run: Mapping[str, Any]) -> float:
    try:
        total = float(value or 0)
    except (TypeError, ValueError):
        return 0.0
    n = _dataset_n(run)
    return total / n if n else 0.0


def _nested(data: Mapping[str, Any], *keys: str) -> Any:
    current: Any = data
    for key in keys:
        if not isinstance(current, Mapping):
            return ""
        current = current.get(key, "")
    return current


def _model_key(run: Mapping[str, Any]) -> str:
    return str(run.get("model_registry_entry") or run.get("model") or "")


def _metric_delta(baseline: Mapping[str, Any], comparison: Mapping[str, Any], key: str) -> Any:
    left = _metrics(baseline).get(key)
    right = _metrics(comparison).get(key)
    if isinstance(left, int | float) and isinstance(right, int | float):
        return right - left
    return ""


def _parse_valid_rate(run: Mapping[str, Any]) -> float:
    validity = run.get("parse_validity", {})
    if not isinstance(validity, Mapping):
        return 0.0
    totals = [stats for stats in validity.values() if isinstance(stats, Mapping)]
    total = sum(stats.get("total", 0) or 0 for stats in totals)
    valid = sum(stats.get("valid", 0) or 0 for stats in totals)
    return valid / total if total else 0.0


def _baseline_evidence_available(status: str, run: Mapping[str, Any]) -> str:
    if status == "not_attempted":
        return "not_applicable"
    if run.get("external_baseline"):
        return "mapped_if_supplied"
    return "available_when_span_extracted"


def _comparability_notes(status: str, evidence_available: str) -> str:
    if status == "not_attempted":
        return "field_not_attempted"
    if status in {"partial", "not_implemented"}:
        return "partial_mapping"
    if evidence_available == "not_applicable":
        return "evidence_not_applicable"
    return ""


def _self_consistency_samples(harness: str) -> int | None:
    marker = "_sc"
    if marker not in harness:
        return None
    suffix = harness.rsplit(marker, 1)[-1]
    return int(suffix) if suffix.isdigit() else None


def _select(row: Mapping[str, Any], headers: Sequence[str]) -> dict[str, Any]:
    return {header: row.get(header, "") for header in headers}


def _csv_value(value: Any) -> Any:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, list | dict):
        return json.dumps(value, sort_keys=True)
    return value
