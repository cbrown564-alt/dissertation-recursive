#!/usr/bin/env python3
"""Build dissertation write-up artifacts from reproducible run outputs."""

from __future__ import annotations

import argparse
import csv
import html
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_OUTPUT_DIR = Path("runs/writeup_support")
DEFAULT_EVALUATION_DIR = Path("runs/evaluation")
DEFAULT_ROBUSTNESS_DIR = Path("runs/robustness")
DEFAULT_EXECT_TEXT_ROOT = Path("data/ExECT 2 (2025)/Gold1-200_corrected_spelling")
PRIMARY_METRICS = [
    "schema_valid_rate",
    "quote_presence_rate",
    "quote_validity_rate",
    "temporal_accuracy",
    "medication_full_f1",
    "seizure_type_f1",
    "current_seizure_frequency_accuracy",
    "eeg_accuracy",
    "mri_accuracy",
    "epilepsy_diagnosis_accuracy",
]


def read_json(path: Path) -> Any | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


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


def parse_number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str) and value.strip():
        try:
            return float(value)
        except ValueError:
            return None
    return None


def format_value(value: Any) -> str:
    if isinstance(value, bool):
        return "yes" if value else "no"
    number = parse_number(value)
    if number is not None:
        return f"{number:.3f}"
    if value is None or value == "":
        return "n/a"
    return str(value)


def markdown_table(rows: list[dict[str, Any]], columns: list[str] | None = None) -> str:
    if not rows:
        return "_No rows available._"
    columns = columns or list(rows[0].keys())
    header = "| " + " | ".join(columns) + " |"
    divider = "| " + " | ".join("---" for _ in columns) + " |"
    body = [
        "| " + " | ".join(format_value(row.get(column)).replace("|", "\\|") for column in columns) + " |"
        for row in rows
    ]
    return "\n".join([header, divider, *body])


def load_evaluation(evaluation_dir: Path) -> tuple[dict[str, Any] | None, list[dict[str, str]], dict[str, Any] | None]:
    return (
        read_json(evaluation_dir / "evaluation_summary.json"),
        read_csv_rows(evaluation_dir / "comparison_table.csv"),
        read_json(evaluation_dir / "document_scores.json"),
    )


def load_robustness(robustness_dir: Path) -> tuple[dict[str, Any] | None, list[dict[str, str]], Any | None]:
    return (
        read_json(robustness_dir / "robustness_summary.json"),
        read_csv_rows(robustness_dir / "label_preserving_degradation.csv"),
        read_json(robustness_dir / "label_changing_validity.json"),
    )


def load_secondary(secondary_dirs: list[Path]) -> list[dict[str, Any]]:
    analyses = []
    for directory in secondary_dirs:
        json_yaml = read_json(directory / "json_yaml_summary.json")
        model_comparison = read_json(directory / "model_comparison_summary.json")
        if json_yaml is not None:
            analyses.append(
                {
                    "directory": str(directory),
                    "kind": "json_vs_yaml_to_json",
                    "summary": json_yaml,
                    "table": read_csv_rows(directory / "json_yaml_comparison_table.csv"),
                }
            )
        if model_comparison is not None:
            analyses.append(
                {
                    "directory": str(directory),
                    "kind": "model_family_comparison",
                    "summary": model_comparison,
                    "table": read_csv_rows(directory / "model_comparison_table.csv"),
                }
            )
    return analyses


def select_columns(rows: list[dict[str, Any]], wanted: list[str]) -> list[dict[str, Any]]:
    selected = []
    for row in rows:
        selected.append({column: row.get(column) for column in wanted if column in row})
    return selected


def claim_rows(
    evaluation_summary: dict[str, Any] | None,
    robustness_summary: dict[str, Any] | None,
    secondary: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows = []
    if evaluation_summary:
        rows.append(
            {
                "claim_area": "Primary event-first comparison",
                "artifact": "evaluation_summary.json",
                "evidence": f"{len(evaluation_summary.get('summaries', []))} system summaries",
                "bounded_claim": "Supports S2 versus E2/E3 comparisons for schema, evidence, temporal, field, cost, and latency metrics.",
            }
        )
    if robustness_summary:
        rows.append(
            {
                "claim_area": "Robustness under perturbation",
                "artifact": "robustness_summary.json",
                "evidence": f"{len(robustness_summary.get('label_preserving_degradation', []))} label-preserving rows",
                "bounded_claim": "Supports degradation claims by perturbation type; label-changing cases remain validity checks rather than ordinary accuracy rows.",
            }
        )
    for item in secondary:
        rows.append(
            {
                "claim_area": item["kind"],
                "artifact": str(Path(item["directory"]) / ("json_yaml_summary.json" if item["kind"].startswith("json") else "model_comparison_summary.json")),
                "evidence": f"{len(item.get('table', []))} reporting rows",
                "bounded_claim": "Supports secondary analysis only; does not displace the primary event-first reliability comparison.",
            }
        )
    if not rows:
        rows.append(
            {
                "claim_area": "Artifact availability",
                "artifact": "none",
                "evidence": "No recognized run summaries found",
                "bounded_claim": "Run evaluation, robustness, or secondary-analysis commands before making empirical claims.",
            }
        )
    return rows


def incorrect_field_names(score: dict[str, Any]) -> list[str]:
    field_scores = score.get("field_scores", {})
    incorrect = []
    for field_name, field_score in field_scores.items():
        if isinstance(field_score, dict) and field_score.get("correct") is False:
            incorrect.append(field_name)
        elif isinstance(field_score, dict) and {"tp", "fp", "fn"} <= set(field_score) and (
            field_score.get("fp") or field_score.get("fn")
        ):
            incorrect.append(field_name)
    return incorrect


def field_score_value(field_score: dict[str, Any]) -> float:
    if "correct" in field_score:
        return 1.0 if field_score.get("correct") is True else 0.0
    f1 = parse_number(field_score.get("f1"))
    if f1 is not None:
        return f1
    return 0.0


def document_score_value(score: dict[str, Any]) -> float:
    if not score.get("available"):
        return 0.0
    field_scores = score.get("field_scores", {})
    values = [
        field_score_value(field_score)
        for field_score in field_scores.values()
        if isinstance(field_score, dict)
    ]
    field_mean = sum(values) / len(values) if values else 0.0
    temporal = parse_number(score.get("temporal_scores", {}).get("accuracy"))
    quote_validity = parse_number(score.get("quote_validity", {}).get("rate"))
    schema = 1.0 if score.get("schema_valid") else 0.0
    components = [field_mean, schema]
    if temporal is not None:
        components.append(temporal)
    if quote_validity is not None:
        components.append(quote_validity)
    return sum(components) / len(components)


def evidence_issue_summary(score: dict[str, Any]) -> str:
    issues = []
    quote_validity = score.get("quote_validity", {})
    if quote_validity.get("invalid_quote_count"):
        issues.append(f"{quote_validity.get('invalid_quote_count')} invalid quote(s)")
    for field_name, item in score.get("semantic_support", {}).items():
        if isinstance(item, dict) and item.get("present") and item.get("gold_overlap") is False:
            issues.append(f"{field_name}: quote valid but no gold overlap")
        if isinstance(item, dict) and item.get("field_count") and item.get("supported_count") == 0:
            issues.append(f"{field_name}: extracted items lack gold-overlap evidence")
    return "; ".join(issues) if issues else "no evidence-specific issue flagged"


def quote_error_class(score: dict[str, Any], incorrect: list[str]) -> str:
    quote_validity = score.get("quote_validity", {})
    if quote_validity.get("invalid_quote_count"):
        return "quote_invalid"
    if incorrect:
        return "quote_valid_but_semantically_wrong_or_missing"
    return "no_field_error"


def failure_mode_tags(score: dict[str, Any]) -> list[str]:
    tags = []
    if not score.get("available"):
        tags.append("missing_output")
    if not score.get("schema_valid"):
        tags.append("schema_or_parse")
    if score.get("quote_validity", {}).get("invalid_quote_count"):
        tags.append("evidence_selection")
    temporal = score.get("temporal_scores", {})
    checked = temporal.get("checked_count") or 0
    correct = temporal.get("correct_count") or 0
    if checked and correct < checked:
        tags.append("temporality")
    for field_name in incorrect_field_names(score):
        if field_name in {"medication_name", "medication_full", "seizure_type"}:
            tags.append("normalization_or_missingness")
        elif field_name in {"current_seizure_frequency", "seizure_frequency_type_linkage"}:
            tags.append("temporality_or_frequency_normalization")
        elif field_name in {"eeg", "mri"}:
            tags.append("investigation_ambiguity")
        elif field_name == "epilepsy_diagnosis":
            tags.append("diagnosis_normalization")
    return sorted(set(tags)) or ["none_flagged"]


def read_aggregation_log(event_run_dir: Path, document_id: str, comparator: str) -> dict[str, Any] | None:
    if comparator != "E2":
        return None
    path = event_run_dir / document_id / "e2_aggregation_log.json"
    if not path.exists():
        return None
    return read_json(path)


def event_failure_stage(
    event_score: dict[str, Any],
    event_run_dir: Path,
    comparator: str,
) -> str:
    document_id = str(event_score.get("document_id"))
    incorrect = incorrect_field_names(event_score)
    if comparator == "E3":
        if not event_score.get("schema_valid"):
            return "constrained_aggregation_schema_or_parse"
        return "constrained_aggregation_or_extraction_review_needed"
    log = read_aggregation_log(event_run_dir, document_id, comparator)
    if not isinstance(log, dict):
        return "aggregation_log_unavailable"
    missing_fields = set(log.get("final_fields_without_event_support", []))
    if any(field in missing_fields for field in incorrect):
        return "extraction_failure_missing_event_support"
    if log.get("conflict_decisions"):
        return "aggregation_failure_conflict_resolution"
    if incorrect and (log.get("selected_event_ids") or log.get("ignored_event_ids")):
        return "aggregation_failure_or_event_normalization"
    return "no_event_first_failure_flagged"


def score_by_document(document_scores: dict[str, Any], system: str) -> dict[str, dict[str, Any]]:
    rows = document_scores.get(system, [])
    if not isinstance(rows, list):
        return {}
    return {
        str(row.get("document_id")): row
        for row in rows
        if isinstance(row, dict) and row.get("document_id")
    }


def artifact_path_for_system(
    run_root: Path,
    direct_run_dir: Path | None,
    event_run_dir: Path | None,
    system: str,
    document_id: str,
) -> str:
    if system == "S2":
        base = direct_run_dir or run_root / "direct_baselines"
        return str(base / "S2" / document_id / "canonical.json")
    if system == "S3":
        base = direct_run_dir or run_root / "direct_baselines"
        return str(base / "S3" / document_id / "canonical.json")
    if system == "E2":
        base = event_run_dir or run_root / "event_first"
        return str(base / document_id / "e2_canonical.json")
    if system == "E3":
        base = event_run_dir or run_root / "event_first"
        return str(base / document_id / "e3_canonical.json")
    return ""


def paired_error_analysis_examples(
    document_scores: dict[str, Any] | None,
    limit: int,
    run_root: Path,
    direct_run_dir: Path | None = None,
    event_run_dir: Path | None = None,
    source_text_root: Path = DEFAULT_EXECT_TEXT_ROOT,
) -> list[dict[str, Any]]:
    if not isinstance(document_scores, dict):
        return []
    direct = score_by_document(document_scores, "S2")
    event_run_dir = event_run_dir or run_root / "event_first"
    rows = []
    per_category_limit = max(1, limit)
    for comparator in ("E2", "E3"):
        event = score_by_document(document_scores, comparator)
        candidates = []
        for document_id in sorted(set(direct) & set(event)):
            s2_score = direct[document_id]
            event_score = event[document_id]
            s2_value = document_score_value(s2_score)
            event_value = document_score_value(event_score)
            candidates.append((event_value - s2_value, document_id, s2_score, event_score))

        category_specs = [
            ("event_first_improves_over_s2", sorted(candidates, reverse=True)),
            ("s2_outperforms_event_first", sorted(candidates)),
            (
                "all_systems_fail",
                sorted(
                    [
                        (max(document_score_value(s2), document_score_value(event_score)), document_id, s2, event_score)
                        for _, document_id, s2, event_score in candidates
                        if incorrect_field_names(s2) and incorrect_field_names(event_score)
                    ]
                ),
            ),
        ]
        for category, ranked in category_specs:
            added = 0
            for delta_or_score, document_id, s2_score, event_score in ranked:
                if category == "event_first_improves_over_s2" and delta_or_score <= 0:
                    continue
                if category == "s2_outperforms_event_first" and delta_or_score >= 0:
                    continue
                s2_incorrect = incorrect_field_names(s2_score)
                event_incorrect = incorrect_field_names(event_score)
                score_delta = document_score_value(event_score) - document_score_value(s2_score)
                rows.append(
                    {
                        "category": category,
                        "comparator": comparator,
                        "document_id": document_id,
                        "s2_score": f"{document_score_value(s2_score):.3f}",
                        "event_score": f"{document_score_value(event_score):.3f}",
                        "score_delta_event_minus_s2": f"{score_delta:.3f}",
                        "s2_incorrect_fields": ", ".join(s2_incorrect) if s2_incorrect else "none",
                        "event_incorrect_fields": ", ".join(event_incorrect) if event_incorrect else "none",
                        "s2_failure_modes": ", ".join(failure_mode_tags(s2_score)),
                        "event_failure_modes": ", ".join(failure_mode_tags(event_score)),
                        "event_failure_stage": event_failure_stage(event_score, event_run_dir, comparator),
                        "s2_quote_error_class": quote_error_class(s2_score, s2_incorrect),
                        "event_quote_error_class": quote_error_class(event_score, event_incorrect),
                        "s2_evidence_issue": evidence_issue_summary(s2_score),
                        "event_evidence_issue": evidence_issue_summary(event_score),
                        "source_text_path": str(source_text_root / f"{document_id}.txt"),
                        "s2_artifact": artifact_path_for_system(run_root, direct_run_dir, event_run_dir, "S2", document_id),
                        "event_artifact": artifact_path_for_system(run_root, direct_run_dir, event_run_dir, comparator, document_id),
                        "aggregation_log": str(event_run_dir / document_id / "e2_aggregation_log.json") if comparator == "E2" else "n/a",
                    }
                )
                added += 1
                if added >= per_category_limit:
                    break
    return rows


def error_examples(document_scores: dict[str, Any] | None, limit: int) -> list[dict[str, Any]]:
    if not isinstance(document_scores, dict):
        return []
    examples = []
    for system, scores in document_scores.items():
        if not isinstance(scores, list):
            continue
        for score in scores:
            if not isinstance(score, dict):
                continue
            errors = score.get("errors", [])
            incorrect = incorrect_field_names(score)
            if not errors and not incorrect:
                continue
            examples.append(
                {
                    "system": system,
                    "document_id": score.get("document_id"),
                    "schema_valid": score.get("schema_valid"),
                    "quote_validity_rate": score.get("quote_validity", {}).get("rate"),
                    "incorrect_fields": ", ".join(incorrect) if incorrect else "n/a",
                    "errors": "; ".join(str(error) for error in errors[:2]) if errors else "n/a",
                }
            )
            if len(examples) >= limit:
                return examples
    return examples


def metric_plot_svg(rows: list[dict[str, Any]], output_path: Path) -> bool:
    plot_rows = []
    for row in rows:
        system = row.get("system") or row.get("condition")
        if not system:
            continue
        for metric in PRIMARY_METRICS:
            value = parse_number(row.get(metric))
            if value is not None:
                plot_rows.append((str(system), metric, max(0.0, min(1.0, value))))
    if not plot_rows:
        return False

    width = 980
    row_height = 22
    left = 270
    right = 40
    top = 36
    height = top + row_height * len(plot_rows) + 32
    bar_width = width - left - right
    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        '<text x="20" y="24" font-family="Arial, sans-serif" font-size="16" font-weight="700">Primary Evaluation Metrics</text>',
        f'<line x1="{left}" x2="{left + bar_width}" y1="{top - 8}" y2="{top - 8}" stroke="#222"/>',
    ]
    for index, (system, metric, value) in enumerate(plot_rows):
        y = top + index * row_height
        label = html.escape(f"{system} {metric}")
        fill = "#2f6f73" if system.startswith("E") else "#8d5a2b"
        lines.extend(
            [
                f'<text x="20" y="{y + 14}" font-family="Arial, sans-serif" font-size="12">{label}</text>',
                f'<rect x="{left}" y="{y + 3}" width="{bar_width}" height="12" fill="#e8ecec"/>',
                f'<rect x="{left}" y="{y + 3}" width="{bar_width * value:.1f}" height="12" fill="{fill}"/>',
                f'<text x="{left + bar_width + 8}" y="{y + 14}" font-family="Arial, sans-serif" font-size="12">{value:.3f}</text>',
            ]
        )
    lines.append("</svg>")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return True


def build_tables_markdown(
    evaluation_rows: list[dict[str, str]],
    robustness_rows: list[dict[str, str]],
    secondary: list[dict[str, Any]],
    plot_written: bool,
) -> str:
    evaluation_columns = ["system", "documents_available", *PRIMARY_METRICS, "mean_latency_ms", "mean_estimated_cost_usd"]
    robustness_columns = [
        "system",
        "perturbation_id",
        "available",
        "delta_schema_valid_rate",
        "delta_quote_validity_rate",
        "delta_medication_full_f1",
        "delta_current_seizure_frequency_accuracy",
        "delta_mri_accuracy",
    ]
    sections = [
        "# Dissertation Tables",
        "",
        "Generated from reproducible run artifacts. Replace smoke-test runs with final validation runs before using these values in chapter prose.",
        "",
        "## Primary Evaluation",
        "",
        markdown_table(select_columns(evaluation_rows, evaluation_columns)),
    ]
    if plot_written:
        sections.extend(["", "![Primary evaluation metric plot](evaluation_metric_plot.svg)"])
    sections.extend(
        [
            "",
            "## Robustness",
            "",
            markdown_table(select_columns(robustness_rows[:30], robustness_columns)),
        ]
    )
    for item in secondary:
        sections.extend(
            [
                "",
                f"## Secondary: {item['kind'].replace('_', ' ').title()}",
                "",
                markdown_table(item.get("table", [])),
            ]
        )
    return "\n".join(sections) + "\n"


def build_methods_markdown(manifest: dict[str, Any], claims: list[dict[str, Any]], examples: list[dict[str, Any]]) -> str:
    sections = [
        "# Methods And Results Traceability Notes",
        "",
        "## Artifact Inventory",
        "",
        markdown_table(manifest["artifacts"]),
        "",
        "## Claim Support Matrix",
        "",
        markdown_table(claims),
        "",
        "## Chapter-Ready Method Notes",
        "",
        "- The evaluation chapter should name the split, systems, prompts, schema version, and run directories recorded in the manifest.",
        "- Primary quantitative claims should come from the evaluation summary, with evidence and temporal metrics reported separately from field correctness.",
        "- Robustness claims should distinguish label-preserving degradation from label-changing validity checks.",
        "- Secondary analyses should be described as bounded checks of output format and model family, not as a broad model leaderboard.",
        "",
        "## Error Analysis Seeds",
        "",
        "Rows are selected from paired S2 versus E2/E3 validation scores. They include event-first wins, direct-baseline wins, and shared failures so chapter prose can explain the headline metrics with concrete documents.",
        "",
        markdown_table(examples),
    ]
    return "\n".join(sections) + "\n"


def artifact_row(label: str, path: Path) -> dict[str, Any]:
    bytes_value = path.stat().st_size if path.exists() and path.is_file() else None
    return {
        "label": label,
        "path": str(path),
        "exists": path.exists(),
        "bytes": bytes_value,
    }


def command_build(args: argparse.Namespace) -> int:
    evaluation_dir = Path(args.evaluation_dir)
    robustness_dir = Path(args.robustness_dir)
    secondary_dirs = [Path(item) for item in args.secondary_dir]
    output_dir = Path(args.output_dir)
    run_root = Path(args.run_root) if args.run_root else evaluation_dir.parent
    direct_run_dir = Path(args.direct_run_dir) if args.direct_run_dir else None
    event_run_dir = Path(args.event_run_dir) if args.event_run_dir else None

    evaluation_summary, evaluation_rows, document_scores = load_evaluation(evaluation_dir)
    robustness_summary, robustness_rows, label_changing = load_robustness(robustness_dir)
    secondary = load_secondary(secondary_dirs)

    output_dir.mkdir(parents=True, exist_ok=True)
    plot_written = metric_plot_svg(evaluation_rows, output_dir / "evaluation_metric_plot.svg")
    claims = claim_rows(evaluation_summary, robustness_summary, secondary)
    examples = paired_error_analysis_examples(
        document_scores,
        args.error_examples,
        run_root=run_root,
        direct_run_dir=direct_run_dir,
        event_run_dir=event_run_dir,
        source_text_root=Path(args.source_text_root),
    )
    if not examples:
        examples = error_examples(document_scores, args.error_examples)
    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "inputs": {
            "run_root": str(run_root),
            "evaluation_dir": str(evaluation_dir),
            "robustness_dir": str(robustness_dir),
            "secondary_dirs": [str(item) for item in secondary_dirs],
            "direct_run_dir": str(direct_run_dir) if direct_run_dir else str(run_root / "direct_baselines"),
            "event_run_dir": str(event_run_dir) if event_run_dir else str(run_root / "event_first"),
            "source_text_root": str(Path(args.source_text_root)),
        },
        "artifacts": [
            artifact_row("primary_evaluation_summary", evaluation_dir / "evaluation_summary.json"),
            artifact_row("primary_evaluation_table", evaluation_dir / "comparison_table.csv"),
            artifact_row("primary_document_scores", evaluation_dir / "document_scores.json"),
            artifact_row("robustness_summary", robustness_dir / "robustness_summary.json"),
            artifact_row("robustness_degradation_table", robustness_dir / "label_preserving_degradation.csv"),
            artifact_row("robustness_label_changing_validity", robustness_dir / "label_changing_validity.json"),
            *[
                artifact_row(f"secondary_{index}_{item['kind']}", Path(item["directory"]))
                for index, item in enumerate(secondary, start=1)
            ],
        ],
        "counts": {
            "evaluation_rows": len(evaluation_rows),
            "robustness_rows": len(robustness_rows),
            "label_changing_validity_rows": len(label_changing) if isinstance(label_changing, list) else 0,
            "secondary_analyses": len(secondary),
            "error_examples": len(examples),
        },
    }

    write_json(output_dir / "writeup_manifest.json", manifest)
    write_csv(output_dir / "claim_support_matrix.csv", claims)
    write_csv(output_dir / "error_analysis_examples.csv", examples)
    (output_dir / "dissertation_tables.md").write_text(
        build_tables_markdown(evaluation_rows, robustness_rows, secondary, plot_written),
        encoding="utf-8",
    )
    (output_dir / "methods_traceability.md").write_text(
        build_methods_markdown(manifest, claims, examples),
        encoding="utf-8",
    )

    print(f"wrote {output_dir / 'writeup_manifest.json'}")
    print(f"wrote {output_dir / 'dissertation_tables.md'}")
    print(f"wrote {output_dir / 'methods_traceability.md'}")
    if plot_written:
        print(f"wrote {output_dir / 'evaluation_metric_plot.svg'}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    build = subparsers.add_parser("build", help="Create write-up support artifacts from existing run outputs.")
    build.add_argument("--evaluation-dir", default=str(DEFAULT_EVALUATION_DIR))
    build.add_argument("--robustness-dir", default=str(DEFAULT_ROBUSTNESS_DIR))
    build.add_argument("--secondary-dir", action="append", default=[], help="Directory containing a secondary-analysis summary.")
    build.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    build.add_argument("--error-examples", type=int, default=8)
    build.add_argument("--run-root", help="Run root used to construct artifact paths; defaults to the evaluation directory parent.")
    build.add_argument("--direct-run-dir", help="Direct-baseline artifact directory; defaults to RUN_ROOT/direct_baselines.")
    build.add_argument("--event-run-dir", help="Event-first artifact directory; defaults to RUN_ROOT/event_first.")
    build.add_argument("--source-text-root", default=str(DEFAULT_EXECT_TEXT_ROOT))
    build.set_defaults(func=command_build)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
