# Archived Entrypoints and Maintained Commands

**Date:** 2026-05-12  
**Status:** Maintained routing guide for post-consolidation work

This document marks the boundary between the maintained dissertation pipeline
spine and frozen exploratory entrypoints. Archived files remain in place so
historical run artifacts can still be reproduced, imported, and audited. They
should not be the place where new shared abstractions are added.

## Maintained Spine

New work should prefer these surfaces:

| Need | Maintained surface |
| --- | --- |
| Corrected ExECTv2 scoring | `src/core/scoring.py` |
| Dataset split and identifier loading | `src/core/datasets.py` |
| JSON, CSV, and text helpers | `src/core/io.py` |
| Benchmark labels | `src/core/labels.py` |
| H6/H6fs/H6full prompt contracts | `src/core/prompts.py` |
| Canonical H6/H6fs/H6full projection | `src/core/projection.py` |
| Run manifest helpers | `src/core/manifests.py` |
| Evidence resolving | `src/evidence_resolver.py` |
| Maintained local candidate runner | `scripts/run_evidence_resolver_scored_batch.py` |
| ExECT Explorer model overlay export | `exect-explorer/scripts/build_model_overlay.py` |

The canonical maintained local candidate is:

```bash
python scripts/run_evidence_resolver_scored_batch.py \
  --canonical-dir runs/local_models/stage_l5_35b_full/calls/qwen_35b_local/H6fs_benchmark_only_coarse_json \
  --split validation \
  --limit 40 \
  --output-dir runs/evidence_resolver/scored_batch
```

The canonical Explorer overlay export is:

```bash
python exect-explorer/scripts/build_model_overlay.py \
  --model-output-dir runs/evidence_resolver/scored_batch/resolved \
  --comparison-report runs/evidence_resolver/scored_batch/comparison_report.json \
  --run-manifest runs/evidence_resolver/scored_batch/run_manifest.json \
  --output exect-explorer/public/data/model_overlays/h6fs_ev_validation.json
```

## Archived Phase Entrypoints

These files are frozen research artifacts. They may still be run when
reproducing a named historical result, but new functionality should be routed
through the maintained spine above.

| Archived file | Historical purpose | Current replacement for new work |
| --- | --- | --- |
| `src/model_expansion.py` | Powerful-model expansion phases, harness diagnostics, and compatibility exports | `src/core/prompts.py`, `src/core/projection.py`, `scripts/run_evidence_resolver_scored_batch.py` |
| `src/local_event_first.py` | EL0/EL1/EL2 local event-first investigation | Maintained H6fs evidence-resolver runner |
| `src/multi_agent.py` | MA_v1 four-role exploratory pipeline | Treat as research lead; maintained default remains H6fs evidence-resolver |
| `src/multi_agent_exploration.py` | MA_v2 verifier/corrector and matched-budget exploration | Treat as research lead; prompt contracts remain frozen under `prompts/multi_agent_v2/` |
| `src/recovery_experiments.py` | Phase 4 S4/S5 recovery prompt experiments | `src/core/scoring.py`, `src/core/prompts.py`, maintained runner |
| `src/dashboard_export.py` | Original aggregate-results dashboard exporter | ExECT Explorer overlay contract and exporter |
| `scripts/run_evidence_resolver_dev_pilot.py` | Early Option-C deterministic resolver pilot | `scripts/run_evidence_resolver_scored_batch.py` |
| `scripts/run_evidence_resolver_fallback_pilot.py` | Early LLM fallback grounding pilot | `scripts/run_evidence_resolver_scored_batch.py --fallback` |
| `scripts/run_evidence_resolver_robustness.py` | Targeted resolver perturbation mini-run | Maintained scored runner plus focused regression tests |

## Preservation Rule

Do not move or delete archived entrypoints unless a reproduction plan has been
checked against historical run documentation. In-place archival markers are
intentional: they make the maintenance boundary visible while keeping old
imports and commands stable.
