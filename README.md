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
- [Direct baselines](docs/09_direct_baselines.md) - S1/S2/S3 prompt, parse, repair, validation, evidence scoring, and logging harness.
- [Event-first pipeline](docs/10_event_first_pipeline.md) - E1 event extraction plus E2/E3 aggregation.
- [Evaluation harness](docs/11_evaluation_harness.md) - S2 versus E2/E3 scoring over existing run outputs.
- [Robustness tests](docs/12_robustness_tests.md) - perturbation generation, robustness runs, and degradation tables.
- [Secondary analyses](docs/13_secondary_analyses.md) - controlled JSON versus YAML-to-JSON and bounded model-family comparisons.

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

## Milestone 3 Exit Check

Install dependencies first in a local virtual environment:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

Then run the small-subset stub harness:

```bash
.venv/bin/python src/direct_baselines.py run \
  --provider stub \
  --limit 2 \
  --output-dir runs/milestone_3_stub
```

## Milestone 7 Exit Check

Run the controlled format-comparison smoke check against existing stub outputs:

```bash
.venv/bin/python src/secondary_analyses.py json-yaml \
  --split development \
  --limit 2 \
  --direct-run-dir runs/milestone_3_stub \
  --output-dir runs/milestone_7_json_yaml_stub
```

Run the bounded model-family comparison smoke check against existing stub
outputs:

```bash
.venv/bin/python src/secondary_analyses.py model-compare \
  --split development \
  --limit 2 \
  --condition local_stub:local:S2:runs/milestone_3_stub \
  --condition frontier_stub:closed:S3:runs/milestone_3_stub \
  --reference-condition local_stub \
  --output-dir runs/milestone_7_model_compare_stub
```

## Current Priority

The next work should run the bounded Milestone 7 comparisons on real matched
validation artifacts, then move into dissertation write-up support.
