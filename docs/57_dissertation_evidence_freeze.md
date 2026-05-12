# Dissertation Evidence Freeze

**Date:** 2026-05-12  
**Status:** Initial maintained validation artifact frozen  
**Scope:** H6fs local extraction plus deterministic Option-C evidence resolving on the ExECTv2 validation split.

---

## 1. Canonical Artifact

The maintained local deployment candidate is now represented by:

```text
runs/evidence_resolver/scored_batch/
```

This directory was produced with:

```bash
python scripts/run_evidence_resolver_scored_batch.py \
  --canonical-dir runs/local_models/stage_l5_35b_full/calls/qwen_35b_local/H6fs_benchmark_only_coarse_json \
  --split validation \
  --limit 40 \
  --output-dir runs/evidence_resolver/scored_batch
```

Generated files:

- `comparison_report.json` - baseline H6fs versus evidence-resolved H6fs metrics.
- `run_manifest.json` - input hashes, component versions, scorer version, and resolver mutation policy.
- `resolved/*.json` - evidence-resolved canonical extractions.

The corresponding Explorer overlay is:

```text
exect-explorer/public/data/model_overlays/h6fs_ev_validation.json
```

It was generated with:

```bash
python exect-explorer/scripts/build_model_overlay.py \
  --canonical-dir runs/evidence_resolver/scored_batch/resolved \
  --comparison-report runs/evidence_resolver/scored_batch/comparison_report.json \
  --run-manifest runs/evidence_resolver/scored_batch/run_manifest.json \
  --limit 40 \
  --output exect-explorer/public/data/model_overlays/h6fs_ev_validation.json
```

---

## 2. Headline Metrics

Validation documents: 40.

| Metric | H6fs baseline | H6fs + evidence resolver |
| --- | ---: | ---: |
| Quote presence | 0.0000 | 0.7778 |
| Quote validity | 0.0000 | 1.0000 |
| Medication name F1 | 0.8519 | 0.8519 |
| Seizure type F1 | 0.3878 | 0.3878 |
| Seizure type F1, collapsed | 0.5926 | 0.5926 |
| Epilepsy diagnosis accuracy | 0.8000 | 0.8000 |

Evidence resolver counts:

- Deterministic hits: 119.
- Fallback hits: 0.
- Ungrounded values: 34.
- Total present values: 153.

The resolver is therefore behaving as intended for this artifact: it improves
auditability by adding evidence spans without changing extracted values or
field-level scores.

---

## 3. Scoring Method Note

This artifact uses `scorer_version = exectv2_corrected_2026_05_12`.

The dissertation methods section should describe the corrected scoring layer as
part of the measurement contribution:

- null-string filtering in gold loading;
- ASM synonym expansion;
- collapsed benchmark seizure labels;
- per-component medication scoring;
- loose seizure-frequency matching;
- explicit quote presence and quote-validity reporting.

These corrections should be framed as evaluation repairs for noisy,
multi-source clinical gold standards, not as model-specific post-processing.

---

## 4. Recommended Audit Pass

Use ExECT Explorer with `h6fs_ev_validation.json` to classify the 34 ungrounded
values and the major field disagreements into:

- model extraction error;
- gold-standard ambiguity or annotation gap;
- normalization/scoring boundary;
- evidence resolver miss.

The highest-value fields for the first pass are seizure type, seizure
frequency, and medication tuples, because they carry the main methodological
claims and the clearest remaining disagreement modes.
