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

    evaluation_summary, evaluation_rows, document_scores = load_evaluation(evaluation_dir)
    robustness_summary, robustness_rows, label_changing = load_robustness(robustness_dir)
    secondary = load_secondary(secondary_dirs)

    output_dir.mkdir(parents=True, exist_ok=True)
    plot_written = metric_plot_svg(evaluation_rows, output_dir / "evaluation_metric_plot.svg")
    claims = claim_rows(evaluation_summary, robustness_summary, secondary)
    examples = error_examples(document_scores, args.error_examples)
    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "inputs": {
            "evaluation_dir": str(evaluation_dir),
            "robustness_dir": str(robustness_dir),
            "secondary_dirs": [str(item) for item in secondary_dirs],
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
    build.set_defaults(func=command_build)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
