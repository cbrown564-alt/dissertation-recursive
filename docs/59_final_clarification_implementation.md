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

## Next Implementation Slices

1. Add raw-output metrics where direct raw scoring is possible without applying
   canonical projection.
2. Add evidence-support scoring separate from quote validity.
3. Down-select the 168-condition full-factorial skeleton into a costed
   40-document final run plan.
