"""Generate an h008-style adjudication worksheet from a broader-field run record.

Usage:
    python scripts/generate_adjudication_worksheet.py \
        --run project_state/runs/<experiment_id>.json \
        --data data/synthetic_data_subset_1500.json \
        --n 25 \
        --out-dir docs/adjudication

Outputs:
    <out-dir>/<stem>_scoring.csv    -- blank scoring sheet
    <out-dir>/<stem>_reference.md   -- letter + extractions reference
"""

import argparse
import csv
import json
import re
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

EVIDENCE_GRADES = (
    "exact_span",
    "overlapping_span",
    "section_level",
    "wrong_temporal_status",
    "unsupported",
    "missing_evidence",
)

SCORE_OPTIONS = "Y / N / P"
NORM_OPTIONS = "Y / N / NA"


def load_run(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_data_index(path: Path) -> dict[int, dict]:
    rows = json.loads(path.read_text(encoding="utf-8"))
    return {r["source_row_index"]: r for r in rows}


def resolve_capsule_path(path_text: str) -> Path:
    path = Path(path_text)
    if path.is_absolute():
        return path
    return ROOT / path


def default_run_path() -> Path:
    runs_dir = ROOT / "project_state" / "runs"
    candidates = sorted(
        runs_dir.glob("*.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    if candidates:
        return candidates[0]
    raise FileNotFoundError(
        "No run record found under project_state/runs. Run scripts/run_h008_guarded.py "
        "or pass --run with a row-level run JSON."
    )


def letter_text(data_row: dict) -> str:
    # The full clinic letter is stored in the 'clinic_date' field.
    return data_row.get("clinic_date", "")


def truncate(text: str, max_chars: int = 120) -> str:
    text = " ".join(text.split())
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rstrip() + "…"


def slugify(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "_", value).strip("_").lower()
    return slug or "adjudication"


def items_from_row(row: dict, letter_num: int, source_idx: int) -> list[dict]:
    """Return one scoring record per extracted item (SF + broader fields)."""
    items = []

    # Seizure frequency
    items.append(
        {
            "row_num": letter_num,
            "source_row_index": source_idx,
            "field": "seizure_frequency",
            "item_num": 1,
            "gold_value": row.get("gold_sf_label", ""),
            "extracted_value": row.get("predicted_sf_label", ""),
            "temporal_status": "current",
            "evidence_text": "(see letter — SF field uses internal model reasoning)",
            "sf_exact_match": "YES" if row.get("sf_exact_match") else "NO",
            "sf_monthly_match": "YES" if row.get("sf_monthly_rate_match") else "NO",
            "value_correct": "",
            "status_correct": "",
            "normalization_correct": "",
            "evidence_grade": "",
            "notes": "",
        }
    )

    # Current medications
    for i, med in enumerate(row.get("current_medications", []), start=1):
        value = f"{med.get('drug_name','')} {med.get('dose_text','')}".strip()
        items.append(
            {
                "row_num": letter_num,
                "source_row_index": source_idx,
                "field": "current_medications",
                "item_num": i,
                "gold_value": "",
                "extracted_value": value,
                "temporal_status": med.get("status", ""),
                "evidence_text": truncate(med.get("evidence", ""), 200),
                "sf_exact_match": "",
                "sf_monthly_match": "",
                "value_correct": "",
                "status_correct": "",
                "normalization_correct": "",
                "evidence_grade": "",
                "notes": "",
            }
        )

    # Seizure types
    for i, st in enumerate(row.get("seizure_types", []), start=1):
        items.append(
            {
                "row_num": letter_num,
                "source_row_index": source_idx,
                "field": "seizure_types",
                "item_num": i,
                "gold_value": "",
                "extracted_value": f"{st.get('description','')} [onset={st.get('onset','')}]",
                "temporal_status": st.get("status", ""),
                "evidence_text": truncate(st.get("evidence", ""), 200),
                "sf_exact_match": "",
                "sf_monthly_match": "",
                "value_correct": "",
                "status_correct": "",
                "normalization_correct": "",
                "evidence_grade": "",
                "notes": "",
            }
        )

    # Investigations
    for i, inv in enumerate(row.get("investigations", []), start=1):
        items.append(
            {
                "row_num": letter_num,
                "source_row_index": source_idx,
                "field": "investigations",
                "item_num": i,
                "gold_value": "",
                "extracted_value": f"{inv.get('investigation_type','')} — {inv.get('result','')}",
                "temporal_status": inv.get("status", ""),
                "evidence_text": truncate(inv.get("evidence", ""), 200),
                "sf_exact_match": "",
                "sf_monthly_match": "",
                "value_correct": "",
                "status_correct": "",
                "normalization_correct": "",
                "evidence_grade": "",
                "notes": "",
            }
        )

    return items


def write_csv(items: list[dict], path: Path) -> None:
    fieldnames = [
        "row_num",
        "source_row_index",
        "field",
        "item_num",
        "gold_value",
        "extracted_value",
        "temporal_status",
        "evidence_text",
        "sf_exact_match",
        "sf_monthly_match",
        "value_correct",
        "status_correct",
        "normalization_correct",
        "evidence_grade",
        "notes",
    ]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(items)


def _format_items_for_md(row: dict) -> str:
    lines = []

    # SF
    gold = row.get("gold_sf_label", "?")
    pred = row.get("predicted_sf_label", "?")
    exact = "✓" if row.get("sf_exact_match") else "✗"
    monthly = "✓" if row.get("sf_monthly_rate_match") else "✗"
    lines.append(f"**SF** gold=`{gold}` | pred=`{pred}` | exact={exact} monthly={monthly}")

    for med in row.get("current_medications", []):
        v = f"{med.get('drug_name','')} {med.get('dose_text','')}".strip()
        ev = med.get("evidence", "")[:120]
        lines.append(f"  **med** `{v}` status={med.get('status','')} | ev: _{ev}_")

    for st in row.get("seizure_types", []):
        desc = st.get("description", "")
        onset = st.get("onset", "")
        ev = st.get("evidence", "")[:120]
        lines.append(f"  **sz_type** `{desc}` onset={onset} | ev: _{ev}_")

    for inv in row.get("investigations", []):
        t = inv.get("investigation_type", "")
        r = inv.get("result", "")
        ev = inv.get("evidence", "")[:120]
        lines.append(f"  **inv** `{t}` result={r} | ev: _{ev}_")

    return "\n".join(lines)


def write_markdown_reference(
    run_rows: list[dict],
    data_index: dict[int, dict],
    n: int,
    run_id: str,
    path: Path,
) -> None:
    lines = [
        f"# Adjudication Reference — {run_id}",
        "",
        f"First {n} rows from the h008 run. Use this alongside the scoring CSV.",
        "",
        "## Scoring guide",
        "",
        f"- **value_correct**: {SCORE_OPTIONS} — Is the extracted value clinically correct?",
        f"- **status_correct**: {SCORE_OPTIONS} — Is the temporal/medication status correct (current / historical / planned)?",
        f"- **normalization_correct**: {NORM_OPTIONS} — Is the normalized label or drug name appropriate?",
        f"- **evidence_grade**: {' / '.join(EVIDENCE_GRADES)}",
        "  - *exact_span*: cited evidence directly supports the value and status.",
        "  - *overlapping_span*: overlaps the right text but includes extra or incomplete wording.",
        "  - *section_level*: points to right section but not the decisive phrase.",
        "  - *wrong_temporal_status*: evidence supports the entity but not the claimed status.",
        "  - *unsupported*: cited evidence does not support the value.",
        "  - *missing_evidence*: value non-empty but no usable evidence supplied.",
        "",
        "---",
        "",
    ]

    for letter_num, row in enumerate(run_rows[:n], start=1):
        src_idx = row["source_row_index"]
        data_row = data_index.get(src_idx, {})
        letter = letter_text(data_row)

        lines.append(f"## Letter {letter_num:02d} — source_row_index={src_idx}")
        lines.append("")
        lines.append("### Extractions")
        lines.append("")
        lines.append(_format_items_for_md(row))
        lines.append("")
        lines.append("### Letter text")
        lines.append("")
        lines.append("```")
        # Wrap at 100 chars for readability
        wrapped = "\n".join(
            textwrap.fill(line, width=100) if len(line) > 100 else line
            for line in letter.split("\n")
        )
        lines.append(wrapped)
        lines.append("```")
        lines.append("")
        lines.append("---")
        lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate an h008-style adjudication worksheet")
    parser.add_argument(
        "--run",
        default="",
        help="Row-level run JSON. Defaults to the newest JSON in project_state/runs.",
    )
    parser.add_argument("--data", default="data/synthetic_data_subset_1500.json")
    parser.add_argument("--n", type=int, default=25)
    parser.add_argument("--out-dir", default="docs/adjudication")
    parser.add_argument(
        "--stem",
        default="",
        help="Optional output filename stem; defaults to a run-derived slug plus row count.",
    )
    args = parser.parse_args()

    run_path = resolve_capsule_path(args.run) if args.run else default_run_path()
    run = load_run(run_path)
    data_index = load_data_index(resolve_capsule_path(args.data))

    run_id = run.get("experiment_id", run_path.stem)
    run_rows = run["rows"]
    slice_rows = run_rows[: args.n]

    out_dir = resolve_capsule_path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    stem = args.stem.strip() or f"{slugify(run_id)}_{args.n:02d}rows_adjudication"
    csv_path = out_dir / f"{stem}_scoring.csv"
    md_path = out_dir / f"{stem}_reference.md"

    all_items: list[dict] = []
    for letter_num, row in enumerate(slice_rows, start=1):
        all_items.extend(items_from_row(row, letter_num, row["source_row_index"]))

    write_csv(all_items, csv_path)
    write_markdown_reference(slice_rows, data_index, args.n, run_id, md_path)

    total_items = len(all_items)
    sf_items = sum(1 for it in all_items if it["field"] == "seizure_frequency")
    med_items = sum(1 for it in all_items if it["field"] == "current_medications")
    st_items = sum(1 for it in all_items if it["field"] == "seizure_types")
    inv_items = sum(1 for it in all_items if it["field"] == "investigations")

    print(f"Wrote {csv_path}")
    print(f"Wrote {md_path}")
    print()
    print(f"Letters:          {args.n}")
    print(f"Total items:      {total_items}")
    print(f"  seizure_freq:   {sf_items}")
    print(f"  medications:    {med_items}")
    print(f"  seizure_types:  {st_items}")
    print(f"  investigations: {inv_items}")


if __name__ == "__main__":
    main()
