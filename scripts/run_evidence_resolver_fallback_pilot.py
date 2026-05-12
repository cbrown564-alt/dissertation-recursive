#!/usr/bin/env python3
"""Small fallback pilot — run Pass 2b LLM fallback on ungrounded values.

Uses a lightweight local model (default gemma4:e4b) to test whether the
fallback recovers enough quotes to reach the promotion gate.

Usage:
    python scripts/run_evidence_resolver_fallback_pilot.py --limit 5
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from evidence_resolver import (
    ResolvableValue,
    ResolverStats,
    build_fallback_prompt,
    deterministic_resolve,
    parse_fallback_response,
    resolve_evidence_hybrid,
)
from intake import preprocess_document
from model_providers import ModelRequest, OllamaAdapter
from model_registry import DEFAULT_REGISTRY, load_model_specs
from validate_extraction import check_quote_validity


def make_ollama_call(model_id: str = "gemma4:e4b"):
    """Return a model_call callable for the evidence resolver."""
    registry = load_model_specs(DEFAULT_REGISTRY)
    model = None
    for label, m in registry.items():
        if m.provider_model_id == model_id:
            model = m
            break
    if model is None:
        raise ValueError(f"Model {model_id} not found in registry")

    adapter = OllamaAdapter()

    def _call(prompt: str) -> dict:
        request = ModelRequest(
            prompt=prompt,
            model=model,
            harness_id="evidence_resolver_fallback",
            temperature=0.0,
            max_output_tokens=2048,
            schema_mode="json_mode",
        )
        response = adapter.call(request)
        return {
            "text": response.text,
            "tokens_in": response.token_usage.input_tokens or 0,
            "tokens_out": response.token_usage.output_tokens or 0,
            "latency_ms": response.latency_ms,
            "error": response.error,
        }

    return _call


def run_fallback_pilot(args: argparse.Namespace) -> int:
    canonical_dir = Path(args.canonical_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    splits = json.loads(Path(args.splits).read_text(encoding="utf-8"))
    doc_ids = splits.get("validation", [])[: args.limit]

    model_call = make_ollama_call(args.model)
    all_stats: list[ResolverStats] = []
    total_quote_count = 0
    total_valid_quotes = 0
    total_present_fields = 0
    total_with_evidence = 0

    for doc_id in doc_ids:
        canonical_path = canonical_dir / doc_id / "canonical_projection.json"
        if not canonical_path.exists():
            print(f"skip {doc_id}: no canonical projection")
            continue

        canonical = json.loads(canonical_path.read_text(encoding="utf-8"))
        document = preprocess_document(doc_id, Path(args.exect_root))
        source_text = document["text"]

        resolved, stats = resolve_evidence_hybrid(
            canonical,
            source_text,
            model_call=model_call,
            expand_sentence=True,
        )

        quote_total, quote_failures = check_quote_validity(resolved, source_text)
        valid_quotes = quote_total - len(quote_failures)

        fields = resolved.get("fields", {})
        present_count = 0
        with_evidence_count = 0
        for key, field in fields.items():
            if isinstance(field, list):
                for item in field:
                    if isinstance(item, dict) and item.get("missingness") == "present":
                        present_count += 1
                        if item.get("evidence"):
                            with_evidence_count += 1
            elif isinstance(field, dict) and field.get("missingness") == "present":
                present_count += 1
                if field.get("evidence"):
                    with_evidence_count += 1

        total_quote_count += quote_total
        total_valid_quotes += valid_quotes
        total_present_fields += present_count
        total_with_evidence += with_evidence_count

        all_stats.append(stats)
        doc_out = output_dir / "resolved" / f"{doc_id}.json"
        doc_out.parent.mkdir(parents=True, exist_ok=True)
        doc_out.write_text(json.dumps(resolved, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

        print(
            f"{doc_id}: values={stats.total_values} "
            f"det={stats.deterministic_hits} fallback={stats.fallback_hits} "
            f"ung={stats.ungrounded} latency={stats.latency_ms:.0f}ms"
        )

    if not all_stats:
        print("No documents processed.")
        return 1

    total_values = sum(s.total_values for s in all_stats)
    deterministic_hits = sum(s.deterministic_hits for s in all_stats)
    fallback_hits = sum(s.fallback_hits for s in all_stats)
    ungrounded = sum(s.ungrounded for s in all_stats)
    total_latency = sum(s.latency_ms for s in all_stats)

    aggregate = {
        "documents_processed": len(all_stats),
        "total_values": total_values,
        "deterministic_hits": deterministic_hits,
        "fallback_hits": fallback_hits,
        "ungrounded": ungrounded,
        "fallback_rate": round(fallback_hits / total_values, 4) if total_values else 0.0,
        "ungrounded_rate": round(ungrounded / total_values, 4) if total_values else 0.0,
        "quote_presence_rate": round(total_with_evidence / total_present_fields, 4) if total_present_fields else 0.0,
        "quote_validity_rate": round(total_valid_quotes / total_quote_count, 4) if total_quote_count else 0.0,
        "total_latency_ms": round(total_latency, 2),
        "avg_latency_ms_per_doc": round(total_latency / len(all_stats), 2),
    }

    summary_path = output_dir / "aggregate_report.json"
    summary_path.write_text(json.dumps(aggregate, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print("=" * 60)
    print("Evidence Resolver Fallback Pilot (Option C — full hybrid)")
    print("=" * 60)
    print(f"Documents processed: {aggregate['documents_processed']}")
    print(f"Total values:        {aggregate['total_values']}")
    print(f"Deterministic hits:  {aggregate['deterministic_hits']}")
    print(f"Fallback hits:       {aggregate['fallback_hits']}")
    print(f"Ungrounded:          {aggregate['ungrounded']}")
    print(f"Fallback rate:       {aggregate['fallback_rate']:.4f}")
    print(f"Ungrounded rate:     {aggregate['ungrounded_rate']:.4f}")
    print(f"Quote presence:      {aggregate['quote_presence_rate']:.4f}")
    print(f"Quote validity:      {aggregate['quote_validity_rate']:.4f}")
    print(f"Total latency:       {aggregate['total_latency_ms']:.0f} ms")
    print(f"Avg latency/doc:     {aggregate['avg_latency_ms_per_doc']:.0f} ms")
    print(f"Wrote:               {summary_path}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--canonical-dir",
        default="runs/local_models/stage_l5_35b_full/calls/qwen_35b_local/H6fs_benchmark_only_coarse_json",
    )
    parser.add_argument(
        "--output-dir",
        default="runs/evidence_resolver/fallback_pilot_gemma4e4b",
    )
    parser.add_argument("--splits", default="data/splits/exectv2_splits.json")
    parser.add_argument("--exect-root", default="data/ExECT 2 (2025)/Gold1-200_corrected_spelling")
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--model", default="qwen3.6:35b", help="Ollama model tag for fallback.")
    args = parser.parse_args()
    return run_fallback_pilot(args)


if __name__ == "__main__":
    raise SystemExit(main())
