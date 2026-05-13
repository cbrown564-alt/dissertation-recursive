# Final Clarification Study Implementation Notes

**Date:** 2026-05-13  
**Status:** Implementation started  
**Source agenda:** `docs/58_phase_review_research_agenda.md`

## Implemented First Slice

The first implemented slice addresses the prompt artefact concern from the phase
review. Maintained H6-family prompt builders now support two prompt styles:

- `internal`: archived-compatible wording, including harness identifiers and
  benchmark-facing language.
- `clinician`: sanitized wording that removes the `## Harness` section, harness
  identifier, and benchmark terminology while preserving the same JSON shape and
  allowed clinical label set.

The default remains `internal` so existing frozen and archival runs remain
reproducible.

## Entry Points

Audit maintained prompt artefacts:

```bash
python scripts/audit_prompt_artifacts.py \
  --document-id EA0001 \
  --output runs/prompt_artifact_audit/prompt_artifacts.json
```

Run local-model H6-family comparisons with sanitized prompts by adding:

```bash
--prompt-style clinician
```

For example:

```bash
python src/local_models.py stage-l3 \
  --models qwen_35b_local \
  --harnesses H6fs_benchmark_only_coarse_json \
  --split development \
  --limit 40 \
  --prompt-style clinician \
  --output-dir runs/local_models/stage_l3_h6fs_clinician
```

## Current Audit Result

On `EA0001`, the maintained H6, H6fs, and H6full internal prompts expose two
tracked artefacts: harness identity and benchmark terminology. The clinician
variants expose zero tracked artefacts under the current audit rules.

This creates the first controlled A/B axis for the agenda:

> internal-labelled prompt vs sanitized clinician-facing prompt.

## Projection Delta Reporting

The second implemented slice makes deterministic projection visible as an
experimental actor. The new report compares parsed raw model payloads with
their `canonical_projection.json` outputs and records:

- field counts before and after projection;
- dropped and added field counts;
- seizure, diagnosis, EEG, and MRI label changes;
- raw quote-like fields versus projected evidence spans;
- fields whose canonical shape force-labels them as current.

Run it on any existing calls directory that contains `raw_response.txt` and
`canonical_projection.json` pairs:

```bash
python scripts/build_projection_delta_report.py \
  --calls-dir runs/final_full_field/validation/calls \
  --output-dir runs/projection_delta_report/final_full_field_validation
```

Initial retrospective run on `runs/final_full_field/validation/calls` compared
104 documents and found:

- 24 dropped fields after projection;
- 0 added fields after projection;
- 352 fields force-labelled current by projection shape;
- 5 documents with seizure-label changes;
- 22 documents with investigation-label changes;
- 0 raw quote-like fields and 0 projected evidence spans for this no-evidence
  projection run.

This does not replace raw-output scoring, but it creates the necessary audit
surface for deciding which claims depend on projection policy.

## Temporality Challenge Set

The third implemented slice builds a named temporality evaluation slice from
ExECTv2 letters. It uses regex triggers for:

- planned medication;
- previous medication;
- tapering, withdrawal, reduction, or stopping;
- dose escalation or titration;
- PRN/rescue medication;
- split morning/evening dose schedules;
- seizure-free status with historical seizure-type context.

Run it with:

```bash
python scripts/build_temporality_challenge_set.py \
  --split validation \
  --output-dir runs/temporality_challenge_set/validation
```

Initial validation-split output found 53 matches across 28 documents:

- dose escalation: 22 matches across 20 documents;
- planned medication: 14 matches across 9 documents;
- previous medication: 4 matches across 4 documents;
- split dose: 3 matches across 2 documents;
- taper or stop: 10 matches across 6 documents.

The row-level CSV preserves document id, category, character offsets, matched
text, and a local snippet for manual review or targeted model reruns.

## Clarification Matrix Config

The fourth implemented slice adds a machine-readable matrix skeleton at
`configs/final_clarification_matrix.yaml`. It names the current experimental
axes explicitly:

- model family;
- harness architecture;
- prompt style;
- projection policy;
- standard validation and hard-slice evaluation sets;
- required outputs, including projection deltas and future evidence-support
  scores.

Summarize it with:

```bash
python scripts/describe_final_clarification_matrix.py \
  --output-dir runs/final_clarification_matrix
```

The current full-factorial skeleton contains 168 conditions before pragmatic
down-selection.

The first pragmatic down-selection is now encoded under `selected_run_plan` in
the matrix config. It keeps 19 40-document conditions covering the core
architecture comparison, internal-vs-clinician prompt artefact A/B pairs,
projection-policy checks, evidence-resolver checks, Gemini Flash quota reruns,
local-family contrasts, and lower-cost frontier baselines. The matrix summary
script now emits:

- `runs/final_clarification_matrix/selected_run_plan.json`
- `runs/final_clarification_matrix/selected_run_plan.csv`

Using the 2026-05-07 model registry prices and rough per-harness token
estimates, the selected plan contains 760 document-runs, 1080 model calls, and
an estimated API spend of USD 8.5768 before local runtime costs.

## Raw Output Scoring

The sixth implemented slice adds direct raw-payload metrics for fields that can
be scored without applying canonical projection. `src/core/raw_output_scoring.py`
extracts model-emitted medication, seizure type, seizure-frequency,
investigation, and diagnosis values from parsed raw payloads and compares them
with ExECTv2 gold labels using the same normalization helpers as the maintained
canonical scorer. These metrics intentionally report `raw_schema_valid_rate` as
0.0 because the payload is not being treated as canonical schema output.

Run it on a calls directory with:

```bash
python scripts/build_raw_output_score_report.py \
  --calls-dir runs/final_full_field/validation/calls \
  --output-dir runs/raw_output_score_report/final_full_field_validation
```

The initial retrospective report scored 135 parseable raw outputs from 207 raw
responses in `runs/final_full_field/validation/calls`. It found raw medication
name F1 0.8739, raw medication full F1 0.6752, raw seizure-type F1 0.3609,
raw collapsed seizure-type F1 0.5580, raw frequency per-letter accuracy
0.1259, EEG accuracy 0.8889, MRI accuracy 0.8296, diagnosis accuracy 0.8074,
and collapsed diagnosis accuracy 0.6519. Empty local-model responses accounted
for the skipped raw outputs.

## Evidence Support Scoring

The fifth implemented slice separates evidence support from quote validity in
the maintained scorer. `src/core/evidence_support.py` adds rule-assisted
per-claim categories:

- `supported`: the quote is valid, overlaps relevant gold evidence, and the
  extracted value is correct under the current field scorer.
- `co_located`: the quote is valid but does not overlap relevant gold evidence.
- `contradicts_gold`: the quote overlaps relevant gold evidence, but the
  extracted value does not match the gold label or value.
- `ambiguous`: the quote is valid, but no adjudicable gold evidence span exists
  for the field group.
- `invalid_quote` and `no_quote`: quote validity or quote presence failed before
  support could be assessed.

`score_document()` now emits an `evidence_support` block alongside the existing
`quote_validity` block, and `flatten_summary()` adds:

- `evidence_support_rate`;
- `evidence_support_decidable_rate`;
- `evidence_support_supported_count`;
- `evidence_support_claim_count`.

This is not a full semantic judge. It is a conservative, reproducible audit
surface for identifying when valid quotes are merely nearby text rather than
claim-supporting evidence.

## Next Implementation Slices

## Controlled Condition Launcher

The seventh implemented slice turns the selected run plan into executable
condition commands. `scripts/run_final_clarification_conditions.py` reads
`selected_run_plan`, materializes per-condition commands, and can optionally
execute them. It dispatches API-backed conditions through
`src/model_expansion.py h6-h7-clean-diagnostic` and local Ollama conditions
through `src/local_models.py stage-l5`. The frontier diagnostic runner now
supports `H6fs_benchmark_only_coarse_json` and `--prompt-style internal|clinician`
so the selected clinician-facing H6fs conditions can run without hand edits.

Dry-run one condition:

```bash
python scripts/run_final_clarification_conditions.py \
  --ids FC19 \
  --output-dir runs/final_clarification
```

Execute it:

```bash
python scripts/run_final_clarification_conditions.py \
  --ids FC19 \
  --output-dir runs/final_clarification \
  --execute
```

The first launched condition was FC19: `gpt_4_1_mini_baseline` with
`H6fs_benchmark_only_coarse_json`, clinician prompt style, on the 40-document
validation split. All 40 calls succeeded and parsed. Projected metrics were:
medication name F1 0.8846, seizure-type F1 0.3495, diagnosis accuracy 0.8000,
benchmark quality 0.6780, mean latency 2104 ms, mean input tokens 754.7, mean
output tokens 42.7, and mean estimated cost USD 0.00037 per document. The raw
pre-projection companion report found raw medication name F1 0.8846, raw
collapsed seizure-type F1 0.5476, raw diagnosis accuracy 0.8000, and no skipped
raw outputs.

## Next Implementation Slices

1. Launch the paired FC01 clinician H6fs condition and FC07 internal-prompt
   condition to quantify the prompt artefact A/B comparison on the same
   40-document validation slice.
