# Performance Recovery Roadmap

The final validation and test runs show that the current extraction systems are
not yet at the standard needed for a strong dissertation claim. This roadmap
reopens the experiment as a performance-recovery programme: identify the major
failure points, test targeted improvements, evaluate rigorously, and loop until
the system reaches a defensible benchmark.

## Benchmark Anchor

Benchmark paper:

- Fang S, Holgate B, Shek A, Winston JS, McWilliam M, Viana PF, Teo JT,
  Richardson MP. "Extracting epilepsy-related information from unstructured
  clinic letters using large language models." Epilepsia. 2025;66:3369-3384.
  DOI: 10.1111/epi.18475.
- PubMed: https://pubmed.ncbi.nlm.nih.gov/40637590/
- PMC landing page: https://pmc.ncbi.nlm.nih.gov/articles/PMC12455391/
- Author code: https://github.com/scfang6/extracting_information_using_LLMs

The paper is not a perfectly matched benchmark because it uses King's College
Hospital clinic letters rather than ExECTv2 synthetic letters, uses its own
annotation categories, and focuses on epilepsy type, seizure type, current
ASMs, and associated symptoms. It is still the right external performance
anchor because it is an epilepsy clinic-letter extraction study with expert
gold labels, precision/recall/F1 reporting, repeated low-temperature runs, and
direct comparison of prompt methods.

Reported benchmark targets to treat as the first recovery bar:

| Task | Best reported LLM target | Human/expert reference | Recovery target for this project |
| --- | --- | --- | --- |
| Epilepsy type / diagnosis type | F1 .80 | F1 .86 | >= .80 F1 or accuracy-equivalent |
| Seizure type | F1 .76 | F1 .78 | >= .76 F1 |
| Current ASMs | F1 .90 | F1 .95 | >= .90 medication-name F1 and >= .80 full-medication tuple F1 |
| Associated symptoms | F1 .63 | F1 .64 | optional extension only |

Additional project-specific gates:

| Layer | Minimum target |
| --- | --- |
| Schema validity | >= .99 |
| Quote validity | >= .99 |
| Temporal accuracy | >= .95 |
| Current seizure-frequency extraction | nonzero immediately, then >= .70 after normalization repair |
| Seizure-frequency type linkage | >= .75 after normalization repair |
| Held-out test policy | one final test run only after recovery choices are frozen |

## Current Failure Snapshot

Held-out test results in `runs/final_test/evaluation/comparison_table.csv`
show the largest gaps:

| System | Medication name F1 | Full medication F1 | Seizure type F1 | Current seizure frequency accuracy | Frequency-type linkage | Epilepsy diagnosis accuracy |
| --- | --- | --- | --- | --- | --- | --- |
| S2 | .842 | .496 | .213 | .000 | .075 | .775 |
| E2 | .704 | .372 | .261 | .000 | .050 | .550 |
| E3 | .829 | .483 | .241 | .000 | .125 | .750 |

The immediate interpretation is not "event-first failed" in a final sense. It
is that the current schema, scorer, normalization, prompts, and aggregation are
not yet aligned well enough with the benchmark-level task. The zero result for
current seizure frequency is especially suspicious and should be treated as a
likely scoring, normalization, or target-definition failure until proven
otherwise.

## Recovery Loop

Each recovery cycle has four stages:

1. Diagnose failure mechanisms on development artifacts only.
2. Implement one or more tightly scoped improvements.
3. Run matched development and validation evaluations with uncertainty
   reporting.
4. Promote, revise, or discard the improvement before starting the next cycle.

Do not use the held-out test split during recovery. The previous test result is
now a baseline observation, not a tuning surface. Once recovery choices are
frozen, create a new held-out final run root and clearly label it as the
post-recovery final test.

## Phase 0: Benchmark Reconciliation

Purpose: make sure the project is trying to match the benchmark fairly.

Actions:

- Read the benchmark paper and supplementary materials closely enough to map
  its labels to the current schema.
- Inspect the author code for task definitions, prompt templates, label lists,
  metric aggregation, and preprocessing.
- Create a benchmark crosswalk:
  - epilepsy type versus current `epilepsy_diagnosis` and diagnosis/type fields;
  - seizure type label set and synonym rules;
  - current ASMs versus medication name-only and full medication tuple scoring;
  - associated symptoms as optional extension, not a primary recovery target.
- Decide which project fields are directly benchmarkable and which are stricter
  than the paper.

Outputs:

- `docs/19_benchmark_crosswalk.md`
- `runs/recovery/benchmark_crosswalk.json`

Exit criterion: every benchmark target in this roadmap has a corresponding
local field, metric, or explicit "not comparable" note.

## Phase 1: Failure Localization

Purpose: identify whether failures come from extraction, normalization,
aggregation, evidence, or scoring.

Actions:

- Build confusion tables for each weak field by system and split.
- For every false positive and false negative, classify the failure source:
  `gold_loader`, `scorer`, `normalizer`, `prompt_extraction`,
  `event_extraction`, `event_aggregation`, `schema_missingness`, or
  `ambiguous_gold`.
- Sample at least 20 documents for each weak task:
  - medication full tuple;
  - seizure type;
  - current seizure frequency;
  - seizure-frequency linkage;
  - epilepsy diagnosis/type.
- Compare S2 raw output, E1 events, E2 aggregation logs, E3 raw output, gold
  spans, and source text side by side.
- Produce a Pareto table showing the top failure causes by field.

Candidate commands:

```bash
.venv/bin/python src/evaluate.py run \
  --split development \
  --systems S2 E2 E3 \
  --direct-run-dir runs/final_validation/direct_baselines \
  --event-run-dir runs/final_validation/event_first \
  --output-dir runs/recovery/baseline_failure_localization
```

Outputs:

- `runs/recovery/failure_pareto.csv`
- `runs/recovery/field_confusions/`
- `runs/recovery/review_packets/`

Exit criterion: at least 80% of weak-field errors are assigned to a concrete,
actionable failure source.

## Phase 2: Gold And Scoring Audit

Purpose: avoid optimizing prompts against a broken or unfair scorer.

Actions:

- Audit the BRAT/gold loader for seizure frequency, medication dose/unit,
  medication frequency, seizure type, EEG/MRI, and diagnosis labels.
- Check whether current seizure frequency is scored against the right temporal
  scope and whether gold annotations actually contain the target form expected
  by the scorer.
- Split medication scoring into:
  - current ASM name detection;
  - dose;
  - unit;
  - frequency;
  - full tuple.
- Split seizure-frequency scoring into:
  - frequency value;
  - period/unit;
  - current/historical/planned temporal scope;
  - seizure-type linkage.
- Add relaxed and strict metrics where appropriate. Strict remains primary
  only after relaxed metrics show that extraction is semantically close.
- Add per-label precision, recall, F1, and support counts for multi-label
  fields, matching the benchmark paper's aggregation style.

Outputs:

- `src/evaluate.py` scorer updates if audit finds scoring defects.
- `runs/recovery/scoring_audit.md`
- `runs/recovery/metric_contract_v2.json`

Exit criterion: a manually reviewed sample of at least 30 field-level cases
matches the intended metric outcome.

## Phase 3: Normalization Repair

Purpose: close the gap between clinically equivalent text and exact-match
scoring.

Actions:

- Build canonical dictionaries and synonym maps for:
  - ASM names, abbreviations, brands, and common misspellings;
  - seizure types and semiology phrases;
  - epilepsy type / diagnosis categories;
  - EEG/MRI normal/abnormal/no-result language;
  - frequency expressions such as "weekly", "every few months", "none since",
    "seizure-free", and ranges.
- Normalize medication dose/unit/frequency as structured components before
  tuple scoring.
- Normalize negated and historical mentions before current-field selection.
- Add explicit uncertainty labels rather than forcing absent or ambiguous text
  into false positives.
- Test normalizers independently with fixture cases before rerunning model
  calls.

Outputs:

- `src/normalization.py`
- `examples/normalization_cases.json`
- `runs/recovery/normalization_unit_report.json`

Exit criterion: normalization fixtures pass and at least half of manually
identified normalization-only errors are corrected without adding new false
positives.

## Phase 4: Prompt And Output Contract Recovery

Purpose: improve extraction quality without changing the research question.

Actions:

- Add benchmark-style direct extraction prompts for the four benchmark-aligned
  tasks:
  - epilepsy type;
  - seizure type;
  - current ASMs;
  - associated symptoms as optional extension.
- Keep output short and task-specific for the benchmark-aligned experiments.
  The Fang et al. paper found direct extraction consistently strong, and
  few-shot prompting did not reliably help complex extraction.
- Create separate prompts for:
  - medication names only;
  - medication full tuple;
  - seizure type;
  - seizure frequency;
  - diagnosis/type.
- Add a verifier pass that receives source text plus extracted candidates and
  returns keep/drop/normalize decisions with evidence quotes.
- Add explicit "current only" medication instructions and examples of
  historical, stopped, planned, and declined medication traps.
- Add explicit "do not infer unless stated" instructions for diagnosis/type and
  seizure type.

Candidate systems:

| ID | Description |
| --- | --- |
| S4 | benchmark-style direct task prompts, merged into canonical JSON |
| S5 | S4 plus candidate verifier |
| E4 | event-first with improved event label taxonomy and normalizer |
| E5 | E4 plus verifier before canonical aggregation |

Outputs:

- `prompts/recovery/`
- `src/recovery_experiments.py`
- `runs/recovery/prompt_matrix.json`

Exit criterion: at least one candidate system improves validation seizure-type
F1, medication-name F1, and diagnosis/type accuracy without reducing quote
validity below .99.

## Phase 5: Aggregation Repair

Purpose: decide whether event-first is genuinely useful after extraction and
normalization have been repaired.

Actions:

- Rework E2 aggregation around ranked candidate events rather than one-shot
  field filling.
- Add deterministic selection rules for:
  - current medication over historical/planned/stopped medication;
  - explicit seizure-type labels over descriptive semiology unless the label
    crosswalk maps the description;
  - latest current seizure-frequency statement over historical frequency;
  - completed EEG/MRI result over requested or pending investigations.
- Record discarded candidates and the reason they were discarded.
- Add an aggregation oracle experiment: feed gold or manually corrected events
  through aggregation to estimate the maximum possible E2 performance if event
  extraction were perfect.

Outputs:

- `runs/recovery/aggregation_oracle/`
- updated `e2_aggregation_log.json` contract
- `runs/recovery/aggregation_error_budget.csv`

Exit criterion: aggregation is no longer the dominant failure source for any
primary weak field.

## Phase 6: Rigorous Evaluation

Purpose: make improvements statistically and operationally credible.

Actions:

- Run all candidate systems on the same fixed development and validation IDs.
- Use near-zero temperature for comparability.
- Repeat each extraction condition at least four times or cache/replay
  deterministic outputs if the provider is deterministic.
- Report precision, recall, F1, standard error, and 95% bootstrap confidence
  intervals for benchmark-aligned tasks.
- Use paired bootstrap or approximate randomization for S2 versus candidate
  comparisons.
- Report parse success, repair rate, schema validity, quote validity, temporal
  accuracy, latency, token usage, and estimated cost separately.
- Keep robustness as a secondary gate after clean validation performance meets
  the benchmark floor.

Candidate command shape:

```bash
.venv/bin/python src/recovery_experiments.py run \
  --split validation \
  --systems S2 S4 S5 E3 E4 E5 \
  --repeats 4 \
  --provider openai \
  --model gpt-4.1-mini \
  --output-dir runs/recovery/validation_cycle_01
```

Outputs:

- `runs/recovery/validation_cycle_*/comparison_table.csv`
- `runs/recovery/validation_cycle_*/field_prf_table.csv`
- `runs/recovery/validation_cycle_*/paired_significance.json`
- `runs/recovery/validation_cycle_*/error_budget.csv`
- `runs/recovery/validation_cycle_*/recovery_decision.json`

Exit criterion: a candidate meets the recovery targets on validation or the
next cycle has a clearly identified failure source to attack.

## Phase 7: Robustness And Generalization Gate

Purpose: prevent overfitting to the clean validation set.

Actions:

- Re-run label-preserving perturbations on the winning candidate and S2.
- Add challenge cases based on failure modes discovered during recovery:
  - current versus historical medication;
  - planned medication changes;
  - negated EEG/MRI findings;
  - seizure-free language;
  - vague seizure frequency;
  - mixed seizure semiology and type labels.
- Require robustness degradation to be no worse than S2 on most
  label-preserving perturbations unless the clean validation gain is large and
  clinically interpretable.
- Keep label-changing perturbations as validity checks, not accuracy scores.

Outputs:

- `runs/recovery/robustness_cycle_*/label_preserving_degradation.csv`
- `runs/recovery/robustness_cycle_*/challenge_validity.json`
- `runs/recovery/robustness_cycle_*/robustness_decision.md`

Exit criterion: the winning candidate is not a brittle prompt that only works
on clean validation letters.

## Phase 8: Freeze And Post-Recovery Test

Purpose: run the recovered system once on held-out data.

Actions:

- Freeze schema, prompts, scorer, normalizers, aggregation, and model choices.
- Record a new validation decision naming the winning recovered system.
- Run one post-recovery held-out test.
- Compare post-recovery test performance against:
  - the original final-test baseline;
  - the benchmark targets;
  - validation expectations.
- If the system still fails the benchmark, report that honestly and loop back
  to Phase 1 with the post-recovery failure analysis. Do not silently retune on
  the test split.

Outputs:

- `runs/recovery/freeze/experiment_freeze.json`
- `runs/recovery/final_validation/validation_decision.json`
- `runs/recovery/final_test/evaluation/comparison_table.csv`
- `runs/recovery/final_test/writeup/claim_package.md`

Exit criterion: the dissertation can state either:

- the recovered system reaches the external benchmark floor for benchmarkable
  tasks;
- the recovered system improves materially but remains below benchmark, with a
  defensible explanation; or
- the benchmark is not reachable under the current dataset/schema/model
  constraints.

## Loop Stop Rules

Continue recovery cycles until one of these is true:

- benchmark-aligned validation targets are met and robustness does not reveal a
  major regression;
- two consecutive cycles identify the same irreducible blocker;
- additional improvements require a new dataset, new annotation layer, or
  supervised fine-tuning outside the dissertation scope;
- cost or latency becomes unacceptable for the stated research question.

## Immediate Next Actions

1. Create the benchmark crosswalk from Fang et al. labels to local schema
   fields.
2. Build failure-localization tables for final validation and development
   artifacts.
3. Audit current seizure-frequency scoring because a zero score across systems
   is unlikely to be informative without root-cause analysis.
4. Split medication scoring into name-only and full-tuple components in the
   write-up and scorer outputs.
5. Start recovery cycle 01 with benchmark-style direct task prompts before
   changing event-first aggregation.
