# Experiment Roadmap

The implementation roadmap is now complete: the project has a schema, intake
contract, extraction harnesses, evaluation, robustness tests, secondary
analyses, write-up support, dashboard export, and a final-run orchestrator.
This document describes how to use that machinery to produce the dissertation
evidence, and where the work naturally ends.

## Natural End Goal

The natural end goal is not a perfect extractor or a broad model leaderboard.
It is a bounded, reproducible answer to this question:

> Does event-first, evidence-grounded extraction improve the reliability of
> structured extraction from epilepsy clinic letters enough to justify its
> added complexity, cost, and latency?

The final dissertation package should contain:

- a frozen schema and scoring contract;
- matched direct and event-first outputs for the same letters;
- primary validation and final test comparisons for S2 versus E2/E3;
- evidence, temporality, parseability, cost, and latency reported separately;
- robustness results for realistic letter perturbations;
- bounded secondary checks for JSON versus YAML-to-JSON and model family;
- error-analysis examples that explain where event-first helps, fails, or adds no value;
- a clear recommendation about whether event-first extraction is worth using for this task.

The experiment is complete when the dissertation can defend one of three
claims:

- **Positive:** event-first extraction improves reliability for temporally complex fields without unacceptable cost.
- **Conditional:** event-first extraction helps only for specific fields or failure modes.
- **Negative:** event-first extraction adds complexity without meaningful reliability gains.

Any of these is a valid endpoint if the evidence is reproducible and bounded.

## Experiment Spine

The experiment has one primary comparison and three supporting analyses.

Primary comparison:

- **S2:** direct canonical JSON extraction with evidence.
- **E2:** event-first extraction followed by deterministic aggregation.
- **E3:** event-first extraction followed by constrained aggregation.

Supporting analyses:

- robustness under label-preserving and label-changing perturbations;
- output-format comparison: S2 JSON versus S3 YAML-to-JSON;
- bounded model-family comparison over matched artifacts.

The central logic is paired: every reported system should be run on the same
document IDs, scored by the same harness, and traced back to the same run root.

## Phase 1: Development Freeze

Purpose: stop changing the experimental target before validation.

Actions:

- Freeze the canonical schema unless a validation-blocking bug is found.
- Freeze target fields to ExECTv2-native scored fields.
- Freeze prompts for S2, S3, E1, and E3.
- Freeze deterministic aggregation rules for E2.
- Confirm that development smoke runs still pass.
- Record any remaining known weaknesses before looking at final test results.

Command:

```bash
.venv/bin/python src/final_runs.py build \
  --provider stub \
  --limit 2 \
  --run-root runs/final_validation_smoke
```

Exit criterion: the full artifact chain completes on a small smoke run and
writes `final_run_manifest.json` with no failures.

## Phase 2: Primary Validation Run

Purpose: produce the main tuning and interpretation evidence on the validation
split.

Actions:

- Run S2/S3 and E1/E2/E3 on the validation split with the selected primary model.
- Score S2 versus E2/E3.
- Inspect field-level differences, not only aggregate means.
- Decide whether E2 or E3 is the primary event-first condition for the final test.
- Record the decision before running the final test split.

Command:

```bash
.venv/bin/python src/final_runs.py build \
  --provider openai \
  --model gpt-4.1-mini \
  --split validation \
  --run-root runs/final_validation
```

Primary outputs:

- `runs/final_validation/direct_baselines/`
- `runs/final_validation/event_first/`
- `runs/final_validation/evaluation/comparison_table.csv`
- `runs/final_validation/evaluation/evaluation_summary.json`
- `runs/final_validation/evaluation/document_scores.json`
- `runs/final_validation/final_run_manifest.json`

Exit criterion: validation results identify the final-test comparison, the
field-level hypotheses, and the main expected event-first benefit.

## Phase 3: Robustness And Challenge Analyses

Purpose: test whether the observed validation behavior survives realistic
letter perturbations.

Actions:

- Use label-preserving perturbations to measure degradation from clean outputs.
- Use label-changing perturbations as validity checks, not ordinary accuracy scores.
- Use Gan 2026 primarily for seizure-frequency stress tests.
- Separate ExECTv2-native claims from extension-field observations.
- Identify whether event-first helps with temporal traps, negation, family history, planned changes, or investigation ambiguity.

Key outputs:

- `runs/final_validation/robustness/label_preserving_degradation.csv`
- `runs/final_validation/robustness/label_changing_validity.json`
- `runs/final_validation/robustness/gan_frequency_summary.csv`
- `runs/final_validation/robustness/robustness_summary.json`

Exit criterion: robustness results can support a bounded claim about where
event-first extraction is more stable, equally stable, or more fragile.

## Phase 4: Secondary Analyses

Purpose: make sure secondary factors do not masquerade as the primary result.

Actions:

- Compare S2 JSON against S3 YAML-to-JSON using matched direct-baseline artifacts.
- Compare a small number of model-family conditions only where matched artifacts exist.
- Report parseability, schema validity, repair, cost, latency, and accuracy separately.
- Keep secondary analyses framed as context for the event-first question, not as a leaderboard.

Key outputs:

- `runs/final_validation/secondary_json_yaml/json_yaml_comparison_table.csv`
- `runs/final_validation/secondary_json_yaml/json_yaml_summary.json`
- `runs/final_validation/secondary_model_compare/model_comparison_table.csv`
- `runs/final_validation/secondary_model_compare/model_comparison_summary.json`

Exit criterion: secondary analyses clarify whether the primary result depends
on output format or model family.

## Phase 5: Error Analysis

Purpose: turn metrics into an interpretable dissertation argument.

Actions:

- Select examples where E2/E3 improves over S2.
- Select examples where S2 outperforms E2/E3.
- Select examples where all systems fail.
- Separate extraction failures from aggregation failures.
- Separate quote-valid-but-semantically-wrong cases from quote-invalid cases.
- Identify whether errors come from temporality, missingness, normalization, evidence selection, or schema/parse failures.

Useful artifacts:

- `document_scores.json`
- `error_analysis_examples.csv`
- `methods_traceability.md`
- dashboard document rows and evidence examples

Exit criterion: the dissertation can explain the headline numbers with
concrete examples.

## Phase 6: Final Test Run

Purpose: run the chosen comparison once on held-out data.

Actions:

- Do not tune prompts, schema, aggregation, or scoring after seeing test results.
- Run the same orchestrated chain on the test split.
- Compare test results against validation expectations.
- Treat unexpected test-set behavior as a finding, not an invitation to retune.

Command:

```bash
.venv/bin/python src/final_runs.py build \
  --provider openai \
  --model gpt-4.1-mini \
  --split test \
  --run-root runs/final_test
```

Exit criterion: the final reported primary comparison is generated from a
single held-out test run with a manifest and matching artifacts.

## Phase 7: Dissertation Claim Package

Purpose: convert the experiment into chapter-ready evidence.

Actions:

- Use `writeup_support.py` outputs for tables, plots, traceability, and error examples.
- Use the dashboard for inspection and presentation, not as a scoring source.
- Write the result as a bounded reliability study.
- State limits clearly: synthetic-data validity, ExECTv2-native labels, no clinical deployment claim, and limited model-family coverage.
- Make the final recommendation about event-first extraction conditional on observed field-level results.

Final outputs:

- methods traceability;
- primary comparison table;
- robustness degradation table;
- secondary-analysis tables;
- evaluation plot;
- error-analysis examples;
- dashboard data bundle;
- final-run manifest.

Exit criterion: every dissertation claim can be traced to a command, run
directory, table, document-level score, or evidence quote.

## Decision Gates

Use these gates to keep the experiment honest:

- **After validation:** choose E2, E3, or both as the final event-first comparator.
- **After robustness:** decide which robustness findings are primary-supporting versus exploratory.
- **After secondary analyses:** decide whether format or model family changes the interpretation.
- **Before final test:** freeze all experimental choices.
- **After final test:** write the result even if it is negative or conditional.

## Reporting Template

The final result should be reported in this order:

1. Dataset, split, model, prompts, schema, and run manifest.
2. Primary S2 versus E2/E3 field-level comparison.
3. Evidence and temporality layers.
4. Parseability, cost, and latency.
5. Robustness and challenge-case behavior.
6. Secondary format and model-family checks.
7. Error analysis with concrete evidence examples.
8. Interpretation, limitations, and recommendation.

The strongest dissertation version is the one where the conclusion is modest,
traceable, and visibly earned by the artifacts.
