#!/usr/bin/env python3
"""Batch-run the evidence resolver on existing canonical projections and score.

This enables direct comparison between H6fs (ungrounded) and H6fs+EV
(evidence-resolved) on the same extraction outputs.

Usage:
    python scripts/run_evidence_resolver_scored_batch.py \
        --canonical-dir runs/local_models/stage_l5_35b_full/calls/qwen_35b_local/H6fs_benchmark_only_coarse_json \
        --split validation \
        --limit 40
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from core.manifests import artifact_record, run_manifest, sha256_text
from core.projection import RELAXED_PROJECTION_VERSION
from core.prompts import build_h6fs_prompt
from core.scoring import SCORER_VERSION
from evidence_resolver import ResolverStats, resolve_evidence_hybrid
from evaluate import load_gold, score_document
from intake import preprocess_document
from model_providers import ModelRequest, OllamaAdapter
from model_registry import DEFAULT_REGISTRY, load_model_specs
from validate_extraction import DEFAULT_SCHEMA, validate_extraction


REQUIRED_COMPARISON_SECTIONS = ("baseline", "resolved")
REQUIRED_COMPARISON_METRICS = (
    "quote_presence",
    "quote_validity",
    "medication_name_f1",
    "seizure_type_f1",
    "seizure_type_f1_collapsed",
    "epilepsy_diagnosis_accuracy",
)
REQUIRED_RESOLVED_METRICS = (
    "deterministic_hits",
    "fallback_hits",
    "ungrounded",
    "total_values",
    "total_fallback_latency_ms",
)


def validate_scored_output_shape(output_dir: Path) -> dict:
    """Validate the public output contract for the maintained scored runner."""
    report_path = output_dir / "comparison_report.json"
    manifest_path = output_dir / "run_manifest.json"
    resolved_dir = output_dir / "resolved"

    missing = [
        str(path)
        for path in (report_path, manifest_path, resolved_dir)
        if not path.exists()
    ]
    if missing:
        raise FileNotFoundError(f"missing scored runner output(s): {missing}")
    if not resolved_dir.is_dir():
        raise NotADirectoryError(f"resolved output is not a directory: {resolved_dir}")

    report = json.loads(report_path.read_text(encoding="utf-8"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    if not isinstance(report.get("documents"), int) or report["documents"] < 1:
        raise ValueError("comparison_report.json must contain documents >= 1")
    for section in REQUIRED_COMPARISON_SECTIONS:
        if section not in report or not isinstance(report[section], dict):
            raise ValueError(f"comparison_report.json missing section: {section}")
        for metric in REQUIRED_COMPARISON_METRICS:
            if metric not in report[section]:
                raise ValueError(f"comparison_report.json missing {section}.{metric}")
    for metric in REQUIRED_RESOLVED_METRICS:
        if metric not in report["resolved"]:
            raise ValueError(f"comparison_report.json missing resolved.{metric}")

    required_manifest_keys = {
        "manifest_version",
        "created_at_utc",
        "name",
        "pipeline_id",
        "inputs",
        "outputs",
        "components",
        "metrics",
    }
    missing_manifest = required_manifest_keys.difference(manifest)
    if missing_manifest:
        raise ValueError(f"run_manifest.json missing keys: {sorted(missing_manifest)}")

    components = manifest.get("components", {})
    resolver = components.get("evidence_resolver", {})
    if resolver.get("mutation_policy") != "evidence arrays only":
        raise ValueError("manifest must record evidence resolver mutation_policy")

    resolved_files = sorted(resolved_dir.glob("*.json"))
    if len(resolved_files) != report["documents"]:
        raise ValueError(
            f"resolved file count {len(resolved_files)} does not match documents {report['documents']}"
        )

    return {"report": report, "manifest": manifest, "resolved_files": [str(path) for path in resolved_files]}


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


def load_split_ids(splits_path: Path, split_name: str, limit: int | None = None) -> list[str]:
    splits = json.loads(splits_path.read_text(encoding="utf-8"))
    ids = splits.get(split_name, [])
    if limit:
        ids = ids[:limit]
    return ids


def run_scored_batch(args: argparse.Namespace) -> int:
    canonical_dir = Path(args.canonical_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    doc_ids = load_split_ids(Path(args.splits), args.split, args.limit)
    gold = load_gold(Path(args.markup_root), Path(args.exect_root))
    schema_path = Path(args.schema)

    model_call = make_ollama_call(args.model) if args.fallback else None

    baseline_scores: list[dict] = []
    resolved_scores: list[dict] = []
    all_stats: list[ResolverStats] = []

    for doc_id in doc_ids:
        canonical_path = canonical_dir / doc_id / "canonical_projection.json"
        if not canonical_path.exists():
            print(f"skip {doc_id}: no canonical projection")
            continue
        if doc_id not in gold:
            print(f"skip {doc_id}: no gold labels")
            continue

        canonical = json.loads(canonical_path.read_text(encoding="utf-8"))
        document = preprocess_document(doc_id, Path(args.exect_root))
        source_text = document["text"]

        # Baseline score (original H6fs)
        baseline_score = score_document(canonical, source_text, gold[doc_id], schema_path)
        baseline_scores.append(baseline_score)

        # Resolve evidence
        resolved, stats = resolve_evidence_hybrid(
            canonical,
            source_text,
            model_call=model_call,
            expand_sentence=True,
        )
        all_stats.append(stats)

        # Validate resolved output (allow present fields without evidence since some may stay ungrounded)
        try:
            validate_extraction(resolved, schema_path, require_present_evidence=False)
            schema_valid = True
        except Exception:
            schema_valid = False

        # Score resolved output
        resolved_score = score_document(resolved, source_text, gold[doc_id], schema_path)
        resolved_scores.append(resolved_score)

        # Write resolved canonical
        doc_out = output_dir / "resolved" / f"{doc_id}.json"
        doc_out.parent.mkdir(parents=True, exist_ok=True)
        doc_out.write_text(json.dumps(resolved, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

        print(
            f"{doc_id}: baseline_qp={baseline_score['quote_presence']['rate']:.2f} "
            f"resolved_qp={resolved_score['quote_presence']['rate']:.2f} "
            f"det={stats.deterministic_hits} fallback={stats.fallback_hits} "
            f"ung={stats.ungrounded} schema_valid={schema_valid}"
        )

    if not baseline_scores:
        print("No documents processed.")
        return 1

    from evaluate import flatten_summary

    baseline_flat = flatten_summary("baseline", baseline_scores)
    resolved_flat = flatten_summary("resolved", resolved_scores)

    def _qp_rate(scores: list[dict]) -> dict:
        present = sum(s["quote_presence"]["present_field_count"] for s in scores)
        with_ev = sum(s["quote_presence"]["with_evidence_count"] for s in scores)
        return {"present_fields": present, "with_evidence": with_ev, "rate": with_ev / present if present else 0.0}

    def _qv_rate(scores: list[dict]) -> dict:
        total = sum(s["quote_validity"]["quote_count"] for s in scores)
        valid = sum(s["quote_validity"]["valid_quote_count"] for s in scores)
        return {"quotes": total, "valid": valid, "rate": valid / total if total else 0.0}

    report = {
        "documents": len(baseline_scores),
        "fallback_model": args.model if args.fallback else None,
        "baseline": {
            "quote_presence": _qp_rate(baseline_scores),
            "quote_validity": _qv_rate(baseline_scores),
            "medication_name_f1": baseline_flat.get("medication_name_f1", 0.0),
            "seizure_type_f1": baseline_flat.get("seizure_type_f1", 0.0),
            "seizure_type_f1_collapsed": baseline_flat.get("seizure_type_f1_collapsed", 0.0),
            "epilepsy_diagnosis_accuracy": baseline_flat.get("epilepsy_diagnosis_accuracy", 0.0),
        },
        "resolved": {
            "quote_presence": _qp_rate(resolved_scores),
            "quote_validity": _qv_rate(resolved_scores),
            "medication_name_f1": resolved_flat.get("medication_name_f1", 0.0),
            "seizure_type_f1": resolved_flat.get("seizure_type_f1", 0.0),
            "seizure_type_f1_collapsed": resolved_flat.get("seizure_type_f1_collapsed", 0.0),
            "epilepsy_diagnosis_accuracy": resolved_flat.get("epilepsy_diagnosis_accuracy", 0.0),
            "deterministic_hits": sum(s.deterministic_hits for s in all_stats),
            "fallback_hits": sum(s.fallback_hits for s in all_stats),
            "ungrounded": sum(s.ungrounded for s in all_stats),
            "total_values": sum(s.total_values for s in all_stats),
            "total_fallback_latency_ms": sum(s.latency_ms for s in all_stats),
        },
    }

    summary_path = output_dir / "comparison_report.json"
    summary_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    manifest_path = output_dir / "run_manifest.json"
    prompt_contract = build_h6fs_prompt({"text": "<SOURCE_LETTER>"}, "H6fs_benchmark_only_coarse_json")
    manifest = run_manifest(
        name="H6fs evidence-resolver scored batch",
        pipeline_id="h6fs_option_c_evidence_resolver",
        inputs={
            "canonical_dir": str(canonical_dir),
            "split": args.split,
            "limit": args.limit,
            "splits": artifact_record(Path(args.splits)),
            "exect_root": str(Path(args.exect_root)),
            "markup_root": str(Path(args.markup_root)),
            "schema": artifact_record(schema_path),
        },
        outputs={
            "output_dir": str(output_dir),
            "comparison_report": artifact_record(summary_path),
            "resolved_dir": str(output_dir / "resolved"),
        },
        components={
            "base_harness": "H6fs_benchmark_only_coarse_json",
            "prompt_contract_sha256": sha256_text(prompt_contract),
            "projection_version": RELAXED_PROJECTION_VERSION,
            "evidence_resolver": {
                "mode": "hybrid_option_c",
                "deterministic_sentence_expansion": True,
                "fallback_enabled": bool(args.fallback),
                "fallback_model": args.model if args.fallback else None,
                "mutation_policy": "evidence arrays only",
            },
            "scorer_version": SCORER_VERSION,
        },
        metrics=report,
    )
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    validate_scored_output_shape(output_dir)

    print("=" * 60)
    print("Evidence Resolver Scored Batch Comparison")
    print("=" * 60)
    print(f"Documents: {report['documents']}")
    print()
    print("Baseline (H6fs, no evidence):")
    print(f"  Quote presence:   {report['baseline']['quote_presence']['rate']:.4f}")
    print(f"  Quote validity:   {report['baseline']['quote_validity']['rate']:.4f}")
    print(f"  Med F1:           {report['baseline']['medication_name_f1']:.4f}")
    print(f"  Sz type F1:       {report['baseline']['seizure_type_f1']:.4f}")
    print(f"  Sz type F1 (col): {report['baseline']['seizure_type_f1_collapsed']:.4f}")
    print(f"  Dx accuracy:      {report['baseline']['epilepsy_diagnosis_accuracy']:.4f}")
    print()
    print("Resolved (H6fs + Evidence Resolver):")
    print(f"  Quote presence:   {report['resolved']['quote_presence']['rate']:.4f}")
    print(f"  Quote validity:   {report['resolved']['quote_validity']['rate']:.4f}")
    print(f"  Med F1:           {report['resolved']['medication_name_f1']:.4f}")
    print(f"  Sz type F1:       {report['resolved']['seizure_type_f1']:.4f}")
    print(f"  Sz type F1 (col): {report['resolved']['seizure_type_f1_collapsed']:.4f}")
    print(f"  Dx accuracy:      {report['resolved']['epilepsy_diagnosis_accuracy']:.4f}")
    print(f"  Deterministic:    {report['resolved']['deterministic_hits']}")
    print(f"  Fallback:         {report['resolved']['fallback_hits']}")
    print(f"  Ungrounded:       {report['resolved']['ungrounded']}")
    print(f"  Fallback latency: {report['resolved']['total_fallback_latency_ms']:.0f} ms")
    print(f"Wrote: {summary_path}")
    print(f"Wrote: {manifest_path}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--canonical-dir", required=True)
    parser.add_argument("--output-dir", default="runs/evidence_resolver/scored_batch")
    parser.add_argument("--splits", default="data/splits/exectv2_splits.json")
    parser.add_argument("--split", default="validation")
    parser.add_argument("--exect-root", default="data/ExECT 2 (2025)/Gold1-200_corrected_spelling")
    parser.add_argument("--markup-root", default="data/ExECT 2 (2025)/MarkupOutput_200_SyntheticEpilepsyLetters")
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--limit", type=int, default=40)
    parser.add_argument("--fallback", action="store_true", help="Enable LLM fallback (requires Ollama).")
    parser.add_argument("--model", default="qwen3.6:35b", help="Fallback model tag.")
    args = parser.parse_args()
    return run_scored_batch(args)


if __name__ == "__main__":
    raise SystemExit(main())
