# Dissertation Recursive

Working materials for a dissertation on reliable, event-first information extraction from epilepsy clinic letters.

The current proposal is [proposal_tight.md](proposal_tight.md). It narrows the project to a training-free reliability evaluation: compare direct structured extraction with an event-first, evidence-grounded pipeline, then evaluate JSON/YAML and open/closed model differences as secondary factors.

## Documentation Map

- [Proposal review](docs/proposal_review.md) - strengths, risks, and immediate decisions from the tightened proposal.
- [Scope and research questions](docs/01_scope_and_research_questions.md) - locked project spine, hypotheses, and exclusions.
- [Canonical schema](docs/02_canonical_schema.md) - target fields, missingness, evidence, temporality, and event objects.
- [Pipeline design](docs/03_pipeline_design.md) - direct baselines, event-first stages, validation, and aggregation.
- [Evaluation protocol](docs/04_evaluation_protocol.md) - datasets, splits, metrics, perturbations, and comparisons.
- [Implementation roadmap](docs/05_implementation_roadmap.md) - practical build order and milestones.
- [Literature review matrix](docs/06_literature_review_matrix.md) - review strands and extraction decisions to support.
- [Canonical JSON Schema](schemas/canonical_extraction.schema.json) - initial machine-readable output contract.
- [Milestone 1 scoring spec](docs/scoring/milestone_1_scoring_spec.md) - first executable validation and scoring contract.
- [Data intake](docs/08_data_intake.md) - dataset manifest, fixed splits, preprocessing, gold loading, and quote-normalization checks.

## Milestone 1 Exit Check

```bash
python3 src/validate_extraction.py \
  examples/sample_canonical_extraction.json \
  --source "data/ExECT 2 (2025)/Gold1-200_corrected_spelling/EA0001.txt" \
  --expectations examples/sample_scoring_expectations.json
```

## Milestone 2 Exit Check

```bash
python3 src/intake.py check-one EA0001 --max-mismatches 10
```

## Current Priority

The next work should implement Milestone 3 direct baselines: S1 direct JSON extraction, S2 direct extraction with evidence, S3 YAML-to-JSON extraction, parse/repair handling, validation, evidence-layer scoring, and logging on a small development subset.
