# Abstention And Granularity Scoring

**Date:** 2026-05-13  
**Status:** Initial scoring layer implemented  
**Source agenda:** `docs/58_phase_review_research_agenda.md`, section 10.4  
**Purpose:** Make seizure-type abstention visible as its own evaluation view rather than hiding it inside strict or collapsed F1.

## What Was Added

The maintained corrected scorer now emits a separate seizure-type abstention and
granularity analysis in addition to the existing:

- strict seizure-type F1;
- collapsed benchmark seizure-type F1; and
- document-level label-set traces.

Implementation entry points:

- `src/core/abstention.py`
- `src/core/scoring.py`
- `tests/test_core_scoring.py`

## Current Classification Rules

The implemented layer is intentionally conservative. It does not try to decide
whether a model's specific inference is clinically reasonable. Instead, it
separates benchmark-behavior categories that the final clarification study can
report explicitly.

For each document, the scorer now classifies seizure-type behavior as one of:

- `correct_abstention`: gold expects `unknown seizure type`, and the prediction
  abstains with `unknown seizure type` rather than emitting a specific type;
- `unsupported_specificity`: gold expects `unknown seizure type`, but the model
  emits one or more specific seizure types;
- `missed_abstention`: gold expects `unknown seizure type`, but the model emits
  no seizure type at all;
- `over_abstention`: gold contains a specific seizure type, but the model
  abstains with `unknown seizure type`;
- `granularity_mismatch`: the strict fine-grained label set differs, but the
  collapsed benchmark label set matches;
- `specificity_match`: the fine-grained label set matches exactly;
- `missing_specific_prediction` or `specificity_error`: residual non-abstention
  disagreement categories.

## Summary Metrics

`flatten_summary()` now reports:

- `seizure_type_abstention_case_count`
- `seizure_type_correct_abstention_rate`
- `seizure_type_correct_abstention_count`
- `seizure_type_missed_abstention_rate`
- `seizure_type_missed_abstention_count`
- `seizure_type_over_abstention_rate`
- `seizure_type_over_abstention_count`
- `seizure_type_unsupported_specificity_rate`
- `seizure_type_unsupported_specificity_count`
- `seizure_type_granularity_mismatch_rate`
- `seizure_type_granularity_mismatch_count`

These are meant to sit alongside strict and collapsed seizure-type F1, not
replace them.

## Interpretation Boundaries

- `unsupported_specificity` is a benchmark-facing label. It does not mean the
  model's inference was clinically absurd.
- `granularity_mismatch` isolates cases where the disagreement is about
  fine-grained ILAE detail rather than the broader collapsed category.
- This first pass does not yet adjudicate "clinically reasonable but
  benchmark-noncompliant" specificity. That remains a later review layer.

## Next Likely Follow-Up

The next natural extension is to materialize per-condition abstention summary
rows and confusion-table views once enough clarification conditions have
completed to support comparative analysis.
