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
- [Dissertation write-up support](docs/14_dissertation_writeup_support.md) - reproducible tables, traceability notes, plots, and error-analysis seeds.
- [Reliability dashboard](docs/15_reliability_dashboard.md) - React dashboard and dashboard-ready data export from run artifacts.
- [Dashboard JSON Schema](schemas/dashboard_data.schema.json) - stable dashboard bundle contract with missingness reasons and artifact metadata.
- [Dashboard product plan](docs/16_dashboard_product_plan.md) - current prototype status, intended full dashboard workflow, and prioritized future work.
- [Experiment roadmap](docs/17_experiment_roadmap.md) - how to use the completed implementation to produce final dissertation evidence.
- [Performance recovery roadmap](docs/18_performance_recovery_roadmap.md) - benchmark recovery plan after weak initial final results.
- [Benchmark crosswalk](docs/19_benchmark_crosswalk.md) - Fang et al. benchmark mapping to local fields and metrics.
- [Powerful model expansion roadmap](docs/20_powerful_model_expansion_roadmap.md) - cost-aware plan for testing stronger models and looser harnesses.

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

## Milestone 8 Exit Check

Generate dissertation-facing tables and traceability notes from existing smoke
artifacts:

```bash
.venv/bin/python src/writeup_support.py build \
  --evaluation-dir runs/milestone_5_stub_eval_final_2 \
  --robustness-dir runs/robustness_smoke_venv \
  --secondary-dir runs/milestone_7_json_yaml_stub \
  --secondary-dir runs/milestone_7_model_compare_stub \
  --output-dir runs/milestone_8_writeup_smoke
```

Build the dashboard data bundle and run the local dashboard:

```bash
.venv/bin/python src/dashboard_export.py build \
  --evaluation-dir runs/milestone_5_stub_eval_final_2 \
  --robustness-dir runs/robustness_smoke_venv \
  --direct-run-dir runs/milestone_3_stub \
  --event-run-dir runs/milestone_4_stub_check_venv_2 \
  --secondary-dir runs/milestone_7_json_yaml_stub \
  --secondary-dir runs/milestone_7_model_compare_stub \
  --output dashboard/public/data/dashboard_data.json

.venv/bin/python src/dashboard_export.py validate dashboard/public/data/dashboard_data.json

cd dashboard
npm install
npm run dev -- --port 5173
```

Dashboard status: the current app is a prototype over a real exported data
contract. It proves that run outputs can feed a downstream dashboard, but the
sidebar, header filters, chart context, evidence drill-down, and document audit
workflow still need product work before it should be treated as a mature
analysis surface. See the [dashboard product plan](docs/16_dashboard_product_plan.md)
for the intended full design and backlog.

## Current Priority

Implementation is complete, and the first final results are now a baseline
observation rather than the end of the project. The current priority is to use
the [performance recovery roadmap](docs/18_performance_recovery_roadmap.md)
and the [powerful model expansion roadmap](docs/20_powerful_model_expansion_roadmap.md)
to test whether stronger models, improved scoring/normalization, and looser
harness contracts can reach benchmark-level performance at an acceptable cost.

Start with a smoke check:

```bash
.venv/bin/python src/final_runs.py build \
  --provider stub \
  --limit 2 \
  --run-root runs/final_validation_smoke
```

For the powerful-model expansion path, run Stage A with stub calls first, then
build the Stage B pilot decision artifacts from that auditable call report:

```bash
.venv/bin/python src/model_expansion.py stage-a-smoke \
  --stub-calls \
  --allow-unavailable \
  --limit 2 \
  --output-dir runs/model_expansion/stage_a_smoke

.venv/bin/python src/model_expansion.py stage-b-dev-pilot \
  --stage-a-dir runs/model_expansion/stage_a_smoke \
  --output-dir runs/model_expansion/stage_b_dev_pilot
```

After promoted validation artifacts exist, build the Stage C validation matrix:

```bash
.venv/bin/python src/model_expansion.py stage-c-validation \
  --evaluation-condition gpt_4_1_mini_baseline:S2:H0_strict_canonical:runs/final_validation/evaluation \
  --evaluation-condition event_first_e2:E2:H0_strict_canonical:runs/final_validation/evaluation \
  --condition-model event_first_e2=gpt_4_1_mini_baseline \
  --output-dir runs/model_expansion/stage_c_validation
```

Then run the primary validation chain:

```bash
.venv/bin/python src/final_runs.py build \
  --provider openai \
  --model gpt-4.1-mini \
  --split validation \
  --run-root runs/final_validation
```

After validation decisions are frozen, run the held-out final test:

```bash
.venv/bin/python src/final_runs.py decide \
  --validation-run-root runs/final_validation \
  --comparator E2 \
  --rationale "Validation results support E2 as the primary event-first comparator."

.venv/bin/python src/final_runs.py build \
  --provider openai \
  --model gpt-4.1-mini \
  --split test \
  --validation-decision runs/final_validation/validation_decision.json \
  --run-root runs/final_test
```

Each run refreshes matched extraction artifacts, primary evaluation, robustness
outputs, secondary analyses, dissertation write-up tables, dashboard data, and
`final_run_manifest.json` under the selected run root. The orchestrator also
writes `experiment_freeze.json` with hashes for schema, prompts, scoring code,
splits, and run settings. Test-split runs are guarded until a validation
decision file records whether E2, E3, or both are the final event-first
comparator.
