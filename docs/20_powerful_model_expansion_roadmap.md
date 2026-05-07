# Powerful Model Expansion Roadmap

The performance-recovery work showed that prompt, schema, normalization, and
aggregation fixes improve the harness, but do not yet produce benchmark-leading
performance. This roadmap expands the experiment from a single primary model
into a controlled, cost-aware model and harness study.

The motivating question is:

> How much extraction reliability is gained by stronger frontier models, and
> does that gain justify the cost, latency, and loss of harness strictness?

The expected outcome is not simply a leaderboard. The dissertation needs a
defensible account of the trade-off between model strength, prompt/output
constraints, evidence discipline, post-processing complexity, and operational
cost.

## Target Model Set

Requested frontier and strong-efficiency models:

| Label | Provider family | Intended role |
| --- | --- | --- |
| `claude_sonnet_4_6` | Anthropic Claude | High-quality frontier comparator |
| `gpt_5_5` | OpenAI GPT | Highest-capability OpenAI comparator |
| `gpt_5_4_mini` | OpenAI GPT | Cost-efficient OpenAI comparator |
| `gemini_3_1_pro` | Google Gemini | High-quality Gemini comparator |
| `gemini_3_1_flash` | Google Gemini | Cost-efficient Gemini comparator |
| `gpt_4_1_mini_baseline` | OpenAI GPT | Existing baseline anchor |

The model labels above are study labels, not permanent API constants. Before
running paid experiments, create a versioned model registry that records:

- exact provider model ID;
- provider API surface and SDK version;
- context window and output limits used;
- supported structured-output mode, if any;
- temperature and decoding parameters;
- input/output/cache pricing snapshot date;
- provider region, account, and billing currency;
- known deprecation or alias behavior.

Do not compare results from mutable aliases unless the resolved model version
is recorded in the run manifest.

## Research Questions

Primary expansion questions:

1. Do stronger frontier models close the gap to the Fang et al. epilepsy-letter
   benchmark on medication names, seizure type, and epilepsy type?
2. Is the best-performing system still event-first, or do stronger models make
   simpler direct extraction competitive or superior?
3. Which models lie on the cost-effectiveness frontier: highest accuracy for a
   given cost and latency budget?
4. Does a looser harness improve high-capability model performance, and if so
   which guarantees are lost?
5. Are cheap strong models such as mini/flash variants good enough after
   normalization and verification, or does the task require the expensive tier?

Secondary questions:

- Does structured output help or hurt compared with natural-language or
  task-specific answers followed by deterministic parsing?
- Are evidence quotes a source of reliability, or do they mostly constrain
  high-end models into worse extraction behavior?
- Does verifier-based post-processing recover most of the frontier-model gain
  while keeping the canonical schema strict?
- Which failure modes remain model-invariant: ambiguous gold, schema mismatch,
  temporal scope, medication tuple granularity, or scorer limitations?

## Harness Strictness Conditions

The current project mostly uses a strict canonical schema with evidence quotes.
This expansion should explicitly test multiple harness contracts.

| ID | Harness condition | Description | Main risk |
| --- | --- | --- | --- |
| `H0_strict_canonical` | Current strict harness | Canonical JSON, project schema, evidence quotes, strict validation | Strong models may spend capacity satisfying schema rather than extracting |
| `H1_repaired_canonical` | Strict target with repair | Same target, but allow robust parse repair and normalization before scoring | Repairs may hide model weaknesses |
| `H2_task_specific` | Benchmark-style task prompts | Separate compact prompts for medication names, seizure type, epilepsy type, frequency, and investigations | Harder to preserve whole-schema consistency |
| `H3_loose_answer_then_parse` | Loose clinical extraction | Let model answer in concise prose or simple lists, then parse into canonical fields deterministically | Parser becomes part of the model system |
| `H4_model_native_structured` | Provider-native structure | Use each provider's best structured-output mechanism with minimal local repair | Provider capabilities may not be comparable |
| `H5_verifier_relaxed` | Candidate plus verifier | Candidate extraction followed by keep/drop/normalize verifier and evidence audit | Doubles or triples model-call cost |

The important comparison is not just accuracy. Each harness must report:

- parse success and repair rate;
- schema validity before and after repair;
- quote presence and quote validity;
- temporal support;
- benchmark-aligned PRF;
- local strict metrics;
- token usage, latency, retries, and estimated cost;
- number and kind of post-processing interventions.

## Candidate Systems

Use a small set of system families rather than every possible combination.

| ID | System | Purpose |
| --- | --- | --- |
| `D0` | Existing S2 direct canonical extraction | Baseline direct extraction |
| `D1` | Task-specific direct extraction | Tests benchmark-style short prompts on stronger models |
| `D2` | Loose answer then deterministic parse | Tests whether high-end models benefit from less schema pressure |
| `D3` | Direct extraction plus verifier | Tests whether verification beats event-first complexity |
| `E0` | Existing E2/E3 event-first systems | Baseline event-first comparison |
| `E1` | Event-first with stronger event extraction only | Tests whether event quality was the bottleneck |
| `E2` | Event-first with verifier before aggregation | Tests whether event-first plus strong verification is worth its cost |
| `N0` | Normalization-only replay | Re-score existing outputs with improved normalization to separate model gain from scorer gain |

Run `D1`, `D2`, `D3`, `E1`, and `E2` only after a small development pilot shows
that the provider adapter and parser are stable.

## Experimental Design

Avoid a full Cartesian product at the start. It will be expensive and hard to
interpret.

### Stage A: Provider And Harness Smoke

Purpose: verify that every model can be called, logged, parsed, and costed.

Actions:

- Add provider adapters for OpenAI, Anthropic, and Google.
- Add a provider-neutral response log contract.
- Run 2 development documents through each target model with `H0`, `H2`, and
  `H3`.
- Record raw provider metadata, token counts, latency, retries, and exact model
  IDs.
- Fail closed if a model cannot produce auditable logs.

Outputs:

- `src/model_providers.py`
- `src/model_registry.py`
- `runs/model_expansion/stage_a_smoke/model_registry_snapshot.json`
- `runs/model_expansion/stage_a_smoke/provider_call_report.csv`

Exit criterion: each target model has at least one successful auditable run, or
is explicitly marked unavailable with the reason and date.

### Stage B: Development Pilot

Purpose: identify promising model/harness pairs cheaply.

Design:

- split: development only;
- documents: 10 to 15, stratified by known hard cases;
- repeats: 1 initially;
- systems: `D0`, `D1`, `D2`, `E0`;
- models: all target models plus `gpt_4_1_mini_baseline`;
- harnesses: `H0`, `H2`, `H3`.

Decision rule:

- Promote a model/harness pair if it improves at least two benchmark-aligned
  fields or materially improves one weak field without parse/evidence collapse.
- Drop a pair if it is dominated by another pair on both accuracy and cost.
- Keep one cheap model even if it is not best, as the cost baseline.

Outputs:

- `runs/model_expansion/stage_b_dev_pilot/comparison_table.csv`
- `runs/model_expansion/stage_b_dev_pilot/cost_effectiveness_frontier.csv`
- `runs/model_expansion/stage_b_dev_pilot/promotion_decision.md`

### Stage C: Validation Matrix

Purpose: evaluate promoted systems rigorously without touching test data.

Design:

- split: validation;
- documents: full validation split;
- repeats: 3 for stochastic model calls where budget allows;
- systems: promoted direct systems plus one event-first variant;
- models: promoted frontier models, promoted efficiency models, and
  `gpt_4_1_mini_baseline`;
- harnesses: at least one strict and one relaxed condition.

Report:

- benchmark-collapsed epilepsy type PRF;
- benchmark-collapsed seizure type PRF;
- medication-name PRF;
- medication full tuple PRF as local strict metric;
- current seizure frequency and linkage as local extension metrics;
- temporal accuracy, quote validity, schema validity;
- cost per document;
- cost per correctly extracted benchmark field;
- latency p50/p95;
- paired bootstrap confidence intervals;
- model/harness interaction effects.

Outputs:

- `runs/model_expansion/stage_c_validation/model_harness_table.csv`
- `runs/model_expansion/stage_c_validation/field_prf_table.csv`
- `runs/model_expansion/stage_c_validation/bootstrap_intervals.json`
- `runs/model_expansion/stage_c_validation/cost_latency_table.csv`
- `runs/model_expansion/stage_c_validation/validation_decision.json`

Exit criterion: select at most two final candidates:

- the best quality candidate;
- the best cost-effective candidate.

### Stage D: Robustness And Constraint Ablation

Purpose: test whether relaxed harness gains are real or brittle.

Actions:

- Re-run promoted candidates on label-preserving perturbations.
- Add constraint ablations:
  - evidence required versus evidence audited after extraction;
  - full canonical schema versus task-specific schema;
  - strict JSON versus provider-native structure;
  - local normalization off versus on;
  - verifier off versus on.
- Track whether relaxed harnesses hallucinate unsupported fields more often.
- Separate accuracy gain from evidence degradation.

Outputs:

- `runs/model_expansion/stage_d_robustness/constraint_ablation_table.csv`
- `runs/model_expansion/stage_d_robustness/label_preserving_degradation.csv`
- `runs/model_expansion/stage_d_robustness/evidence_risk_review.md`

Exit criterion: the final candidate is not merely better on clean validation
because it is ignoring evidence, temporality, or missingness constraints.

### Stage E: Freeze And Final Test

Purpose: run the chosen expanded-model candidates once on held-out test data.

Actions:

- Freeze provider model IDs, prompts, harness mode, parsers, normalizers,
  verifier settings, scorer, and pricing snapshot.
- Run one final test pass for the selected high-quality candidate and selected
  cost-effective candidate.
- Compare against:
  - original `gpt-4.1-mini` final test;
  - performance-recovery candidates;
  - Fang et al. benchmark-aligned targets;
  - validation expectations.
- Do not retune after seeing test results.

Outputs:

- `runs/model_expansion/freeze/experiment_freeze.json`
- `runs/model_expansion/final_test/comparison_table.csv`
- `runs/model_expansion/final_test/cost_effectiveness_frontier.csv`
- `runs/model_expansion/final_test/claim_package.md`

Exit criterion: the dissertation can make a bounded claim about whether
stronger models and/or looser harnesses are worth their cost.

## Cost Accounting

Every run must record enough information to reconstruct cost.

Required fields:

- provider;
- exact model ID;
- input tokens;
- output tokens;
- cache read/write tokens if available;
- number of calls per document;
- retries and repair calls;
- verifier calls;
- wall-clock latency;
- pricing source and date;
- estimated cost in billing currency and USD-equivalent if needed.

Derived cost metrics:

| Metric | Purpose |
| --- | --- |
| Cost per document | Basic operational comparison |
| Cost per benchmark field | Penalizes multi-call systems fairly |
| Cost per correct benchmark field | Accuracy-adjusted cost |
| Marginal cost per F1 point over baseline | Makes frontier gains interpretable |
| Latency per document p50/p95 | Deployment realism |
| Calls per document | Exposes verifier/event-first overhead |

Plot and report the Pareto frontier rather than only the top score.

## Provider Adapter Requirements

The current code is OpenAI-only apart from stubs. The expansion needs a
provider-neutral adapter layer.

Implementation requirements:

- one internal request object for prompt, schema mode, temperature, max output,
  seed if supported, and metadata;
- one internal response object for text, parsed structure, token usage,
  latency, stop reason, retries, provider metadata, and raw response path;
- provider-specific adapters for OpenAI, Anthropic, and Google;
- graceful handling of unsupported features such as seeds or strict structured
  output;
- no provider-specific assumptions inside the evaluator;
- run manifests that include model registry snapshots.

Suggested file additions:

- `src/model_providers.py`
- `src/model_registry.py`
- `src/model_expansion.py`
- `configs/model_registry.yaml`
- `configs/harness_matrix.yaml`

## Scoring And Reporting Changes

The model expansion should not rely only on the current strict local metrics.
Add reporting layers:

- benchmark-collapsed epilepsy type PRF;
- benchmark-collapsed seizure type PRF;
- medication-name PRF with ASM dictionary normalization;
- full medication tuple PRF as a stricter local metric;
- field-level missingness calibration;
- evidence audit results for relaxed harnesses;
- cost and latency tables;
- bootstrap confidence intervals;
- model/harness interaction summaries.

Keep strict canonical metrics in the report even when relaxed harnesses perform
better. Otherwise the experiment cannot say what was gained versus what was
given up.

## Interpretation Rules

Use these rules before writing claims:

- A stronger model "wins" only if it improves accuracy without unacceptable
  evidence, temporal, or schema degradation.
- A relaxed harness "wins" only if post-hoc parsing and evidence audit remain
  transparent and reproducible.
- A high-cost model must be compared against the best cheap frontier/flash/mini
  alternative, not only against `gpt-4.1-mini`.
- Event-first remains worthwhile only if its reliability gain survives when
  direct extraction uses the same stronger model.
- If a model improves benchmark-aligned fields but harms local strict fields,
  report that as a task-specific trade-off.
- If the winning system depends on provider-native structured output, treat
  portability as a limitation.

## Immediate Next Actions

1. Add a provider-neutral model registry and response log contract.
2. Implement Anthropic and Google provider adapters alongside the existing
   OpenAI adapter.
3. Create `H0`, `H2`, and `H3` harness modes for a 2-document smoke run.
4. Build cost accounting into every model call before running the expensive
   matrix.
5. Run Stage A smoke across the requested model set and record exact model IDs,
   availability, token usage, latency, and pricing snapshot date.
6. Run Stage B on development hard cases and promote only non-dominated
   model/harness pairs to validation.
