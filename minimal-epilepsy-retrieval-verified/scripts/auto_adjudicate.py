"""
Auto-adjudicate adjudication sheet rows using gold labels and LLM-as-judge.

Seizure frequency (SF):
  1. Null/empty extraction → score=0
  2. parse_label succeeds on both → compare pragmatic classes (rule-based)
  3. Otherwise → LLM judge for semantic equivalence against gold label

All other field families (current_medications, investigations,
seizure_classification, epilepsy_classification):
  - Batch all items for a (run_id, row_id) in one judge call
  - Context: evidence quotes where available, letter text otherwise
  - Judge scores each item: 1=correct, 0.5=partial, 0=wrong/unsupported

Usage:
  python scripts/auto_adjudicate.py \\
    --adjudication results/adjudication/architecture_ladder_n25_real_provider_2026_05_08.csv \\
    --dataset data/synthetic_data_subset_1500.json \\
    --output results/adjudication/architecture_ladder_n25_real_provider_2026_05_08_adjudicated.csv
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from epilepsy_extraction.data import load_synthetic_subset
from epilepsy_extraction.evaluation import parse_label
from epilepsy_extraction.providers import OpenAIProvider
from epilepsy_extraction.providers.base import ProviderMessage, ProviderRequest

_JUDGE_MODEL = "gpt-5.4-mini-2026-03-17"
_NULL_VALUES = {"", "null", "none", "unknown", "not stated", "not reported", "not documented"}

_SF_SYSTEM = (
    "You are a clinical adjudicator comparing a model's extracted seizure frequency "
    "against a gold standard label. Reply with JSON only: "
    '{"score": "1"|"0.5"|"0", "note": "<one sentence reason>"}. '
    "Score 1 = semantically equivalent, 0.5 = partially correct (right order of magnitude "
    "but wrong specifics), 0 = wrong or cannot be evaluated."
)

_BATCH_SYSTEM = (
    "You are a clinical adjudicator. Given a clinic letter excerpt and a list of extracted "
    "clinical items, score each item for correctness. "
    "Score 1=correct and supported by the text, 0.5=partially correct or ambiguous, "
    "0=wrong, hallucinated, or not supported. "
    'Reply with JSON only: {"scores": [{"idx": <int>, "score": "1"|"0.5"|"0", "note": "<brief reason>"}]}'
)

_FIELD_DESCRIPTIONS = {
    "current_medications": "current medication (name, dose, frequency)",
    "investigations": "clinical investigation or test result (EEG, MRI, blood test, etc.)",
    "seizure_classification": "seizure type, feature, or pattern modifier",
    "epilepsy_classification": "epilepsy type or syndrome",
}


# ── Seizure frequency helpers ────────────────────────────────────────────────

def _is_null(value: str) -> bool:
    return value.strip().lower() in _NULL_VALUES or value.strip().startswith("{")


def _rule_compare(emitted: str, gold: str) -> tuple[str, str] | None:
    try:
        gold_p = parse_label(gold)
        emitted_p = parse_label(emitted)
    except Exception:
        return None
    if gold_p.pragmatic_class == "UNK" or emitted_p.pragmatic_class == "UNK":
        return None
    if gold_p.pragmatic_class == emitted_p.pragmatic_class:
        return "1", f"pragmatic class match ({gold_p.pragmatic_class})"
    return "0", f"pragmatic mismatch: pred={emitted_p.pragmatic_class} gold={gold_p.pragmatic_class}"


def _sf_llm_judge(emitted: str, gold: str, provider: OpenAIProvider) -> tuple[str, str]:
    prompt = f"Gold label: {gold}\nExtracted value: {emitted}\nDo these describe the same seizure frequency?"
    req = ProviderRequest(
        messages=[ProviderMessage(role="system", content=_SF_SYSTEM),
                  ProviderMessage(role="user", content=prompt)],
        model=_JUDGE_MODEL, temperature=0.0, response_format="json",
    )
    resp = provider.complete(req)
    if not resp.ok:
        return "0", f"judge_error: {resp.error.type}"
    try:
        data = json.loads(resp.content)
        return str(data.get("score", "0")), str(data.get("note", ""))
    except Exception:
        return "0", "judge_parse_error"


def adjudicate_sf_row(emitted: str, gold: str, provider: OpenAIProvider) -> tuple[str, str, str]:
    """Return (reference_value, value_score, adjudicator_note)."""
    if _is_null(emitted):
        return gold, "0", "null or missing extraction"
    rule = _rule_compare(emitted, gold)
    if rule:
        return gold, rule[0], rule[1]
    score, note = _sf_llm_judge(emitted, gold, provider)
    return gold, score, f"llm_judge: {note}"


# ── Non-SF batch judge ───────────────────────────────────────────────────────

def _build_context(items: list[dict]) -> str:
    """Build context string from evidence quotes in a batch of items."""
    seen: list[str] = []
    for item in items:
        ev = str(item.get("evidence", "") or "").strip()
        if ev and ev not in seen:
            seen.append(ev)
    return " | ".join(seen) if seen else ""


def _batch_judge(
    items: list[dict],
    letter: str,
    provider: OpenAIProvider,
) -> dict[int, tuple[str, str]]:
    """Judge a batch of non-SF items for one (run_id, row_id). Returns {idx: (score, note)}."""
    context = _build_context(items)
    if not context:
        context = letter[:2000]  # truncate full letter if no evidence quotes

    lines = []
    for i, item in enumerate(items):
        fam_desc = _FIELD_DESCRIPTIONS.get(item["field_family"], item["field_family"])
        lines.append(f'{i}. {fam_desc}: "{item["emitted_value"]}"')

    prompt = (
        f"Clinic letter excerpt:\n{context}\n\n"
        f"Extracted items to score:\n" + "\n".join(lines)
    )
    req = ProviderRequest(
        messages=[ProviderMessage(role="system", content=_BATCH_SYSTEM),
                  ProviderMessage(role="user", content=prompt)],
        model=_JUDGE_MODEL, temperature=0.0, response_format="json",
    )
    resp = provider.complete(req)
    if not resp.ok:
        return {i: ("0", f"judge_error: {resp.error.type}") for i in range(len(items))}
    try:
        data = json.loads(resp.content)
        result = {}
        for s in data.get("scores", []):
            idx = int(s.get("idx", -1))
            if 0 <= idx < len(items):
                result[idx] = (str(s.get("score", "0")), str(s.get("note", "")))
        # fill any missing
        for i in range(len(items)):
            if i not in result:
                result[i] = ("0", "missing_from_response")
        return result
    except Exception:
        return {i: ("0", "judge_parse_error") for i in range(len(items))}


# ── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--adjudication", type=Path, required=True)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    records = load_synthetic_subset(args.dataset)
    gold_index: dict[str, str] = {str(r.row_id): r.gold_label for r in records}
    letter_index: dict[str, str] = {str(r.row_id): r.letter for r in records}

    provider = OpenAIProvider()

    with open(args.adjudication, newline="", encoding="utf-8") as f:
        all_rows = list(csv.DictReader(f))
    fieldnames = list(all_rows[0].keys()) if all_rows else []

    # Index rows by position so we can patch them in-place
    indexed = [dict(r) for r in all_rows]

    # ── Pass 1: SF rows ──────────────────────────────────────────────────────
    sf_indices = [i for i, r in enumerate(indexed) if r["field_family"] == "seizure_frequency"]
    print(f"SF rows: {len(sf_indices)}", file=sys.stderr)
    for n, i in enumerate(sf_indices, 1):
        row = indexed[i]
        gold = gold_index.get(str(row["row_id"]), "")
        if gold:
            ref, score, note = adjudicate_sf_row(row["emitted_value"], gold, provider)
            indexed[i]["reference_value"] = ref
            indexed[i]["value_score"] = score
            indexed[i]["adjudicator_note"] = note
        if n % 25 == 0:
            print(f"  SF: {n}/{len(sf_indices)}", file=sys.stderr)

    # ── Pass 2: non-SF rows, batched by (run_id, row_id) ────────────────────
    non_sf = [(i, r) for i, r in enumerate(indexed) if r["field_family"] != "seizure_frequency"]
    # Group by (run_id, row_id)
    groups: dict[tuple[str, str], list[tuple[int, dict]]] = defaultdict(list)
    for i, r in non_sf:
        groups[(r["run_id"], r["row_id"])].append((i, r))

    print(f"Non-SF batches: {len(groups)} (covering {len(non_sf)} rows)", file=sys.stderr)
    for batch_n, ((run_id, row_id), batch_items) in enumerate(sorted(groups.items()), 1):
        letter = letter_index.get(str(row_id), "")
        items = [r for _, r in batch_items]
        scores = _batch_judge(items, letter, provider)
        for local_idx, (global_idx, _) in enumerate(batch_items):
            score, note = scores.get(local_idx, ("0", "missing"))
            indexed[global_idx]["value_score"] = score
            indexed[global_idx]["adjudicator_note"] = f"llm_judge: {note}"
        if batch_n % 50 == 0:
            print(f"  Non-SF batches: {batch_n}/{len(groups)}", file=sys.stderr)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(indexed)

    total_scored = sum(1 for r in indexed if r.get("value_score"))
    print(json.dumps({
        "output": str(args.output),
        "total_rows": len(indexed),
        "rows_scored": total_scored,
        "sf_rows": len(sf_indices),
        "non_sf_batches": len(groups),
    }, indent=2))


if __name__ == "__main__":
    main()
