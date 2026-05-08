# Seizure Frequency Improvement Workstream

**Date:** 2026-05-08  
**Primary benchmark:** Gan et al. 2026, *Reproducible Synthetic Clinical Letters for Seizure
Frequency Information Extraction* — seizure-frequency-specific extraction with structured labels,
evidence references, and category-level micro-F1. Scaled synthetic CoT fine-tuning achieved
Pragmatic micro-F1 **0.847** with Qwen2.5-14B and **0.858** with MedGemma-4B on a clinician
double-checked independent real-letter test set.

**Secondary benchmark:** Fonferko-Shadrach et al. 2024 (J Biomed Semantics 15:17) — ExECTv2
achieves seizure frequency **per-item F1 = 0.66**, per-letter F1 = 0.68, using the ExECTv2
dataset. Human inter-annotator agreement for seizure frequency was only **0.47** — the lowest
of any annotated entity.

**Goal:** Use the Gan frequency task as the primary development and benchmark target. The
practical target is **Pragmatic micro-F1 >= 0.85** on Gan-style category evaluation, with Purist
micro-F1 reported as the harder secondary metric. ExECTv2 per-letter frequency remains a
crosswalk metric for dissertation continuity.

---

## Benchmark Hierarchy

Gan 2026 is better aligned with a seizure-frequency-specific evaluation than ExECTv2 because
seizure frequency is the central task, not one field among many. The local dataset at
`data/Gan (2026)/synthetic_data_subset_1500.json` contains 1,500 synthetic NHS-style clinic
letters with normalized frequency labels, rationales, and evidence references.

The important caveat is that the local synthetic subset is **not** the paper's clinician
double-checked independent real test set. It is suitable for development, prompt comparison,
normalization work, and synthetic benchmark reporting, but any claim that directly matches
Gan's `0.847`/`0.858` result must state whether evaluation was performed on this released
synthetic subset or on an independent real-letter test set.

ExECTv2 remains useful because it preserves the dissertation's broader field-set continuity
and provides a public epilepsy-letter comparator. However, for seizure frequency specifically,
Gan should drive prompt design, normalization, model selection, and the headline frequency
analysis.

---

## Critical Context from Gan 2026

### What the benchmark measures

The Gan headline score is **not exact string match** on normalized labels such as
`2 per 5 month`. The paper evaluates category-level extraction after converting normalized
frequency labels into seizures/month and then into evaluation bins.

The paper evaluates two category mappings:

1. **Purist:** fine-grained monthly-frequency categories:
   - `<1/6M`
   - `1/6M`
   - `(1/6M,1/M)`
   - `1/M`
   - `(1/M,1/W)`
   - `1/W`
   - `(1/W,1/D)`
   - `>=1/D`
   - `UNK`
   - `NS`

2. **Pragmatic:** coarser clinically useful grouping:
   - `infrequent`: `0 < x <= 1.1` seizures/month
   - `frequent`: `1.1 < x <= 999` seizures/month
   - `UNK`: unknown or no seizure-frequency reference
   - `NS`: explicit no-seizure / seizure-free statements

The main reported metric is **micro-F1**. For single-label multi-class classification this is
equivalent to accuracy, but the paper also reports macro and weighted F1 because class
distribution is imbalanced.

### Published target

The strongest published target to match is the pragmatic micro-F1 from scaled synthetic CoT
fine-tuning:

| Model / setting | Purist micro-F1 | Pragmatic micro-F1 |
|---|---:|---:|
| Qwen2.5-14B, 15,000 synthetic CoT letters | 0.788 | 0.847 |
| MedGemma-4B, 15,000 synthetic CoT letters | 0.787 | 0.858 |

Therefore, our practical target should be **Pragmatic micro-F1 >= 0.85**, with Purist
micro-F1 reported as the harder secondary metric.

### Local Gan subset distribution

From the 1,500-example local subset:

| Pragmatic class | Count |
|---|---:|
| frequent | 757 |
| UNK | 264 |
| infrequent | 256 |
| NS | 223 |

Purist classes are more granular and less balanced:

| Purist class | Count |
|---|---:|
| `(1/W,1/D)` | 354 |
| `UNK` | 264 |
| `NS` | 223 |
| `(1/M,1/W)` | 218 |
| `(1/6M,1/M)` | 163 |
| `>=1/D` | 142 |
| `1/M` | 66 |
| `1/W` | 43 |
| `<1/6M` | 18 |
| `1/6M` | 9 |

### Local implementation

`src/gan_frequency.py` implements:

- loading the 1,500 local Gan examples;
- converting normalized labels to approximate seizures/month;
- mapping labels to Purist and Pragmatic categories;
- producing micro/macro/weighted F1 classification reports for prediction files.

Audit command:

```bash
.venv/bin/python src/gan_frequency.py audit --output-dir runs/gan_frequency/audit
```

Outputs:

- `runs/gan_frequency/audit/gan_gold_labels.csv`
- `runs/gan_frequency/audit/gan_gold_audit.json`

Prediction evaluation command:

```bash
.venv/bin/python src/gan_frequency.py evaluate \
  --predictions runs/gan_frequency/predictions.json \
  --output-dir runs/gan_frequency/evaluation
```

`predictions.json` should be a JSON object keyed by Gan document ID, for example:

```json
{
  "GAN11118": "2 cluster per month, 6 per cluster",
  "GAN16750": "6 per 7 month"
}
```

---

## Critical Context from Fonferko-Shadrach 2024

ExECTv2 is now treated as the **secondary crosswalk benchmark** for seizure frequency. It is
still important because it uses the same broader epilepsy-letter corpus as the rest of the
dissertation evaluation, but it is less focused and less label-rich than Gan for the specific
frequency task.

### What the benchmark measures

ExECTv2's 0.66/0.68 is **not** equivalent to our current `current_seizure_frequency_loose_accuracy`.
Understanding the difference is prerequisite to any model experiment.

**Paper's annotation definition for Seizure Frequency:**
> "Number of seizures, by type if stated (including periods of seizure freedom) since or during
> specific point in time/time period/date, or changes in seizure frequency since/during specified
> time or since last clinic visit."

This captures **all frequency mentions** in the letter — current frequency, historical frequency,
per-seizure-type frequency, and changes since last visit. 260 annotations across 200 letters
(≈1.3 per letter) confirms that multiple mentions per letter are common.

**Paper's scoring:**
- Per-item F1: every mention of seizure frequency correctly extracted (the 0.66 figure)
- Per-letter F1: at least one correct frequency extraction exists in the letter (the 0.68 figure)
- "Correct" = right entity span + correct attributes (type, period, counts)

**Our current scoring:**
- Single-value `current_seizure_frequency_loose_accuracy`
- Normalized to count + period form; matched with `frequency_loose_match()`
- Only the most recent/current frequency is extracted and scored

### Why this matters

The scoring mismatch means our 0.000 strict / 0.075–0.175 loose baseline is not directly
comparable to their 0.66 — they are measuring different things. Before running any model
experiments, Stage F0 must resolve the scoring alignment question.

### What the benchmark tells us about feasibility

| Fact | Implication |
|---|---|
| Human IAA = 0.47 | Even experts disagree; the task is genuinely ambiguous in clinical text |
| ExECTv2 rule-based achieves 0.66 | Pattern matching rules can already beat human agreement |
| Per-letter score (0.68) > per-item score (0.66) | Getting at least one mention right is easier than getting all mentions right |
| Human IAA per-letter not reported | But ExECTv2 per-letter = 0.68 confirms extracting one correct mention per letter is achievable |
| 260 annotations / 200 letters | ~1.3 frequency mentions per letter on average |

LLMs should be able to match or exceed a rule-based system at this task — but only if
scored on comparable terms.

---

## Stage F0: Scoring Alignment and Gold Data Audit

**Purpose:** Determine what scoring approach is comparable to the benchmark, and understand
the gold data distribution before spending tokens on model experiments. This is the most
important stage — it determines whether subsequent results are valid comparisons.

**Cost:** Zero — gold data only, no model calls.

### F0-A: Scoring alignment decision

Three options. Pick one before running any experiments.

**Option 1 — Per-letter binary (simplest, recommended)**
- Score: for each letter, is at least one frequency correctly extracted?
- "Correct" = `frequency_loose_match()` succeeds against any gold frequency annotation for
  that letter.
- Matches the paper's per-letter F1 (0.68 target).
- Does not require multi-annotation extraction — our existing single-value pipeline can score
  against this if the gold is loaded as a set rather than a single value.
- **Implementation:** `current_seizure_frequency_per_letter_accuracy` — iterates all gold
  frequency annotations for the letter and returns 1 if any loose-match the extracted value.

**Option 2 — Per-item multi-annotation (harder, matches ExECTv2's primary item benchmark)**
- Score: extract all frequency mentions; score F1 across all gold annotations.
- Matches the paper's per-item F1 (0.66 target).
- Requires schema and pipeline change: `seizure_frequencies` list, not a single value.
- Event-first (E3) is the natural architecture: each frequency event becomes one item.
- **Implementation:** New `seizure_frequency_items` field; `frequency_items_f1` scorer.

**Option 3 — Keep current loose_accuracy (incomparable, not recommended)**
- Retains `current_seizure_frequency_loose_accuracy` as-is.
- Cannot be directly compared to the 0.66/0.68 benchmark.
- Only defensible if a crosswalk between the two metrics is documented.

**Recommendation:** Keep Option 1 as the ExECTv2 crosswalk metric. Do not optimize primarily
against this metric now that Gan is the frequency-specific benchmark. Implement Option 2 only
if the Gan-optimized system also needs an ExECTv2 per-item transfer analysis.

### F0-B: Gold data distribution audit

Actions:
1. Load all frequency annotations from the ExECTv2 CSV files (all splits).
2. For the 40 validation documents:
   - How many letters have 0 annotations? (these drive the oracle ceiling)
   - How many have 1 annotation? 2+?
   - What formats appear? Rate-based / seizure-free / qualitative / change-since-last-visit
   - How many are temporal ("since last visit") vs. absolute ("2 per month")?
3. For the 40 validation letters, run `parse_frequency_expression()` on each gold annotation.
   Record which patterns fail to parse (these are our normalization gaps).
4. Identify the 10 most common surface forms that our parser currently misses.

**Key question:** For Option 1, do any letters have ONLY historical/comparative annotations
(e.g., "fewer seizures than last visit") with no rate-based annotation? If so, our
per-letter scoring will miscount those as failures when they're actually scorer limitations.

**Outputs:**
- `runs/frequency_workstream/stage_f0/gold_distribution.csv`
  (columns: doc_id, n_annotations, annotation_types, parse_success)
- `runs/frequency_workstream/stage_f0/scoring_decision.md`
  (chosen option + rationale + implementation notes)

---

## Stage F1: Scoring Alignment Implementation

**Purpose:** Implement the chosen scoring option and verify it produces sane numbers on existing
runs before touching any new model calls.

**Actions:**

1. Implement `current_seizure_frequency_per_letter_accuracy` in `src/evaluate.py`:
   - Load the full set of gold frequency annotations for each letter (not just one value).
   - For each letter: `score = 1 if any(frequency_loose_match(extracted, gold) for gold in letter_golds) else 0`.
   - Add to `score_document()`, `flatten_summary()`, and `build_field_prf_table()`.

2. Re-score the existing final_validation and final_test runs (no new model calls):
   - Load output JSONs from `runs/final_validation/` and `runs/final_test/`.
   - Re-run through the updated scorer.
   - Report the new per-letter accuracy alongside the old loose_accuracy.

3. Re-score the corrected_metrics runs in `runs/recovery/corrected_metrics/`.

4. Verify: per-letter accuracy should be ≥ loose_accuracy (it's a strictly easier criterion).
   If it isn't, there's a bug.

**Expected result:** Existing GPT-4.1-mini runs will move from 0.075–0.175 loose to some higher
per-letter value. This establishes the true baseline against the 0.68 benchmark.

**Outputs:**
- `runs/frequency_workstream/stage_f1/rescored_existing_runs.csv`
  (systems × splits × loose_acc × per_letter_acc × benchmark_gap)
- Updated `runs/recovery/corrected_metrics/*/evaluation_summary.json`

**Decision rule:**
- If existing best ExECTv2 per-letter score is low, use the failure analysis to inform Gan prompt
  design, but do not block Gan work on ExECTv2.
- If a Gan-optimized system later improves ExECTv2 per-letter score, report it as transfer.
- If per-letter accuracy is ever below loose accuracy, audit the gold loader before using the
  ExECTv2 crosswalk.

---

## Stage G0: Gan Gold Audit and Metric Lock

**Purpose:** Treat Gan 2026 as the primary seizure-frequency task and lock the metric before
running model calls. This stage is the Gan equivalent of ExECTv2 F0/F1: it makes sure we are
comparing against the paper's category-level benchmark rather than exact-string labels.

**Status:** Implemented in `src/gan_frequency.py`.

**Actions:**

1. Load all usable rows from `data/Gan (2026)/synthetic_data_subset_1500.json`.
2. Extract the gold normalized label from `check__Seizure Frequency Number.seizure_frequency_number[0]`.
3. Convert each label to approximate seizures/month.
4. Map each label into:
   - Purist category;
   - Pragmatic category.
5. Write distribution/audit artifacts.

**Outputs:**

- `runs/gan_frequency/audit/gan_gold_labels.csv`
- `runs/gan_frequency/audit/gan_gold_audit.json`

**Primary metric:** Pragmatic micro-F1.

**Secondary metrics:** Purist micro-F1, macro F1, weighted F1, exact normalized-label match.

**Benchmark target:** Pragmatic micro-F1 >= 0.85, interpreted carefully because the local
1,500-example subset is synthetic and not Gan's clinician double-checked real test set.

---

## Stage G1: Gan Prediction Harness

**Purpose:** Build a frequency-only extraction harness whose output can be scored by
`src/gan_frequency.py evaluate`.

**Status:** Implemented as the `predict` subcommand in `src/gan_frequency.py`.
`Gan_direct_label`, `Gan_cot_label`, `Gan_evidence_label`, `Gan_two_pass`, and
`Gan_fs_hard` are now runnable through the same command. Stub smoke tests verify that each
harness writes predictions, call reports, and Gan category evaluation artifacts without paid
model calls.

**Required output format:** one normalized frequency label per Gan document ID.

Example prediction file:

```json
{
  "GAN11118": "2 cluster per month, 6 per cluster",
  "GAN16750": "6 per 7 month"
}
```

**Prompt target:** produce Gan-style labels, not the canonical ExECTv2 field:

```
Extract the current clinically relevant seizure frequency from this clinic letter.

Return exactly one normalized label using these forms:
- "<n> per <period>"
- "<n1> to <n2> per <period>"
- "<n> cluster per <period>, <m> per cluster"
- "seizure free for <n> month"
- "seizure free for multiple month"
- "unknown"
- "no seizure frequency reference"

Use "unknown" when seizures are mentioned but no specific frequency can be determined.
Use "no seizure frequency reference" when the letter does not mention seizure frequency.
```

**Implementation options:**

- Add a Gan-specific command to `src/model_expansion.py`, or
- create a small focused runner in `src/gan_frequency.py` / a companion script that reads Gan
  examples, calls a model, and writes `predictions.json`.

**Outputs:**

- `runs/gan_frequency/<condition>/predictions.json`
- `runs/gan_frequency/<condition>/call_report.csv`
- `runs/gan_frequency/<condition>/gan_frequency_evaluation.json`
- `runs/gan_frequency/<condition>/gan_frequency_predictions_scored.csv`

Run example:

```bash
.venv/bin/python src/gan_frequency.py predict \
  --model gpt_4_1_mini_baseline \
  --harness Gan_direct_label \
  --output-dir runs/gan_frequency/stage_g1/gpt_4_1_mini_baseline_direct \
  --evaluate
```

Prompt-sweep smoke example:

```bash
.venv/bin/python src/gan_frequency.py predict \
  --stub-calls \
  --limit 2 \
  --harness Gan_two_pass \
  --output-dir runs/gan_frequency/stage_g1/stub_two_pass \
  --evaluate
```

---

## Stage G2: Gan Model × Prompt Sweep

**Purpose:** Establish whether stronger models, event-first reasoning, or Gan-style structured
labels can approach the paper's pragmatic micro-F1 target.

**Status:** Completed on a 50-document deterministic development subset using paid provider
calls. All 12 model × harness conditions completed with 50 prediction rows each and no provider
errors. The run cost about **$4.54** in total.

**Design:**

| Axis | Values |
|---|---|
| Models | `gpt_4_1_mini_baseline` (baseline), `gpt_5_5`, `qwen_35b_local` |
| Harnesses | `Gan_direct_label`, `Gan_cot_label`, `Gan_evidence_label`, `Gan_two_pass` |
| Dataset | Gan local synthetic subset |
| Split | Deterministic development subset; first real sweep used 50 docs |
| Repeats | 1 |
| Primary metric | Pragmatic micro-F1 |
| Secondary | Purist micro-F1, exact normalized-label accuracy, quote/evidence validity |

**Note on `qwen_35b_local`:** replaces Claude Sonnet as the open-weight representative.
This is a natural extension of the local models workstream (doc 22), where qwen3.6:35b H6fs
was the recommended deployment configuration. Including it in G2 directly tests whether the
same local model that matched frontier on ExECTv2 medication F1 can approach frontier on
the Gan frequency task. The OllamaAdapter handles `json_schema` mode by falling back to
`format: "json"` (Ollama's JSON enforcement), and think-suppression (`think: false`,
`/no_think` prefix) is already wired for qwen3 models in `src/model_providers.py`.

**Harness definitions:**

- `Gan_direct_label`: single call; return only the normalized Gan label.
- `Gan_cot_label`: single call; reason internally or in a structured analysis field, then return label.
- `Gan_evidence_label`: return label plus exact evidence quote; score label and audit evidence.
- `Gan_two_pass`: first quote relevant frequency evidence, then normalize to Gan label.

**Outputs:**

- `runs/gan_frequency/stage_g2/comparison_table.csv`
  (model, harness, pragmatic_micro_f1, purist_micro_f1, exact_label_accuracy, cost_per_doc)
- `runs/gan_frequency/stage_g2/promotion_decision.md`

Run example:

```bash
.venv/bin/python src/gan_frequency.py sweep \
  --models gpt_4_1_mini_baseline gpt_5_5 qwen_35b_local \
  --harnesses Gan_direct_label Gan_cot_label Gan_evidence_label Gan_two_pass \
  --limit 50 \
  --output-dir runs/gan_frequency/stage_g2
```

**Decision rule:**

- Promote the best model × harness to Stage G3 if Pragmatic micro-F1 >= 0.75 on the development subset.
- If GPT-4.1-mini is within 0.03 absolute Pragmatic micro-F1 of larger models, use it for subsequent prompt iteration.

**Result:**

| Rank | Condition | Pragmatic micro-F1 | Purist micro-F1 | Exact label accuracy | Est. cost |
|---:|---|---:|---:|---:|---:|
| 1 | `gpt_5_5` + `Gan_cot_label` | **0.80** | **0.76** | 0.54 | $0.62 |
| 2 | `gpt_5_5` + `Gan_direct_label` | 0.76 | **0.76** | **0.60** | $0.62 |
| 3 | `claude_sonnet_4_6` + `Gan_direct_label` | 0.76 | **0.76** | 0.58 | $0.30 |
| 4 | `claude_sonnet_4_6` + `Gan_evidence_label` | 0.74 | 0.70 | 0.54 | $0.31 |
| 5 | `gpt_5_5` + `Gan_evidence_label` | 0.72 | 0.70 | 0.54 | $0.67 |
| 6 | `claude_sonnet_4_6` + `Gan_cot_label` | 0.72 | 0.70 | 0.54 | $0.34 |
| 7 | `claude_sonnet_4_6` + `Gan_two_pass` | 0.66 | 0.64 | 0.48 | $0.47 |
| 8 | `gpt_4_1_mini_baseline` + `Gan_direct_label` | 0.66 | 0.62 | 0.48 | $0.02 |
| 9 | `gpt_4_1_mini_baseline` + `Gan_evidence_label` | 0.58 | 0.52 | 0.36 | $0.02 |
| 10 | `gpt_4_1_mini_baseline` + `Gan_two_pass` | 0.58 | 0.50 | 0.36 | $0.03 |
| 11 | `gpt_4_1_mini_baseline` + `Gan_cot_label` | 0.54 | 0.50 | 0.34 | $0.02 |
| 12 | `gpt_5_5` + `Gan_two_pass` | 0.34 | 0.34 | 0.18 | $1.11 |

Promotion decision: **promote `gpt_5_5` + `Gan_cot_label` to Stage G3**. It exceeded the
0.75 Pragmatic micro-F1 promotion threshold on the 50-document development subset. `gpt_5_5`
two-pass should not be carried forward without debugging: it was the most expensive condition
and had the worst score, with frequent parse errors in the two-pass output path.

---

## Stage G3: Gan Frequency-Focused Prompt Development

**Purpose:** Iterate the best Stage G2 model/harness on hard Gan patterns: clusters, ranges,
seizure-free intervals below or above six months, unknown frequency, no-reference cases, and
multiple concurrent seizure types.

### G3-A: Dedicated Gan Label Harness (`Gan_direct_label`)

Standalone prompt that extracts only the Gan normalized label. This removes competition with
the full canonical schema and aligns directly with the Gan paper's structured output setup.

```
## Task
Extract the current clinically relevant seizure frequency from this epilepsy clinic letter.

## Output format
Return JSON:
{"seizure_frequency_number": "<normalized Gan label>",
 "quote": "<verbatim supporting evidence>"}

Use "unknown" when seizures are mentioned but no specific frequency can be determined.
Use "no seizure frequency reference" when seizure frequency is not mentioned.

## Examples
"Two events over the last five months" → "2 per 5 month"
"3-4 focal aware seizures per month" → "3 to 4 per month"
"clusters twice monthly, six seizures per cluster" → "2 cluster per month, 6 per cluster"
"seizure-free for 12 months" → "seizure free for 12 month"
"seizures are sporadic but frequency unclear" → "unknown"

## Clinical letter
{document_text}
```

Scoring: use `src/gan_frequency.py evaluate` for Purist and Pragmatic category metrics.

### G3-B: Two-Pass Gan Harness (`Gan_two_pass`)

Separates "find the text" from "normalize the label."

- **Pass 1 (extract):** quote every sentence or clause mentioning seizure rate, seizure-free
  status, clusters, unknown frequency, or absence of frequency reference.
- **Pass 2 (normalize):** given only the quoted text plus clinic date when available, normalize
  to exactly one Gan label.

This is closest to Gan's evidence-grounded supervision and should make error review easier.

### G3-C: Hard-Case Few-Shot (`Gan_fs_hard`)

Add examples covering the hardest Gan categories:

```
"No attacks since the last appointment three months ago" → "seizure free for multiple month"
"No seizures for 14 months" → "seizure free for 14 month"
"Sporadic jerks this year, exact count unclear" → "unknown"
"The letter discusses epilepsy but gives no frequency" → "no seizure frequency reference"
"Cluster days twice this month; typically six seizures in 24 h" → "2 cluster per month, 6 per cluster"
```

### G3 Evaluation Design

| Condition | Harness | Model | Calls/doc |
|---|---|---|---|
| G3-A | Gan_cot_label refinement | `gpt_5_5` | 1 |
| G3-B | Gan_direct_label comparison | `gpt_5_5` and/or `claude_sonnet_4_6` | 1 |
| G3-C | Gan_fs_hard | `gpt_5_5` | 1 |
| Baseline | H0 canonical projected to Gan labels | GPT-4.1-mini | 1 |

**Split:** Gan development subset, start with the same 50-document subset for controlled
comparison; expand to 150 docs if G3 prompt changes remain promising.  
**Primary metric:** Pragmatic micro-F1.  
**Decision rule:** Promote the highest Pragmatic micro-F1 condition to Stage G4.

**G3 focus after G2:**

- Improve `gpt_5_5` + `Gan_cot_label` from 0.80 toward the >= 0.85 Pragmatic target.
- Compare against `gpt_5_5` + `Gan_direct_label` because it tied Purist micro-F1 and had
  better exact-label accuracy.
- Keep `claude_sonnet_4_6` + `Gan_direct_label` as a cost-efficient challenger; it matched
  `gpt_5_5` direct on category metrics at roughly half the cost.
- Deprioritize two-pass until the evidence-normalization contract is repaired.

**Outputs:**

- `runs/gan_frequency/stage_g3/comparison_table.csv`
- `runs/gan_frequency/stage_g3/promotion_decision.md`

---

## Stage G4: Gan Full-Subset Run

**Purpose:** Formal evaluation of the best Gan model × prompt combination on the full 1,500
local synthetic examples. These become the dissertation's seizure-frequency-specific synthetic
benchmark numbers.

**Design:**

| Item | Value |
|---|---|
| System | Best model × harness from G2/G3 |
| Split | Full local Gan subset (1,500 docs), or held-out deterministic split if prompts were tuned on part of it |
| Repeats | 1 |
| Primary metric | Pragmatic micro-F1 |
| Secondary | Purist micro-F1, exact label accuracy, evidence quote validity |
| Benchmark target | >= 0.85 Pragmatic micro-F1, with caveat that Gan's published target used independent real letters |

**Also run an ExECTv2 crosswalk** if Gan Pragmatic micro-F1 >= 0.75, to quantify whether
Gan-specific gains transfer to the dissertation's broader ExECTv2 validation set.

**Outputs:**

- `runs/gan_frequency/stage_g4/gan_frequency_evaluation.json`
- `runs/gan_frequency/stage_g4/gan_frequency_predictions_scored.csv`
- `runs/gan_frequency/stage_g4/comparison_vs_baseline.csv`
- Update `docs/phase3_synthesis_report.md` §4 frequency rows

---

## Stage F5: ExECTv2 Per-Item Scoring (Conditional Crosswalk)

**Entry criterion:** Gan Stage G4 reaches strong performance and we need to understand transfer
back to ExECTv2's multi-mention annotation scheme.

**Purpose:** Attempt the harder per-item F1 target (0.66) — scoring every individual frequency
mention, not just requiring one correct per letter.

**Actions:**
1. Implement `seizure_frequency_items_f1` in `src/evaluate.py`:
   - Load all gold annotations as a list.
   - Match extracted items against gold items using `frequency_loose_match()`.
   - Compute standard P/R/F1 across all item pairs.
2. Add `seizure_frequencies` (list) to the canonical schema.
3. Test the best F4 condition (which already extracts a list in H_freq/H7_freq harnesses)
   against the per-item scorer on 40 validation docs.
4. If per-item F1 ≥ 0.60 → this is a publishable result (above human IAA of 0.47).

This stage is explicitly conditional — do not run it if F4 hasn't beaten the per-letter target.

---

## Infrastructure Changes Required

| Change | File | Notes |
|---|---|---|
| `current_seizure_frequency_per_letter_accuracy` | `src/evaluate.py` | Multi-gold per-letter binary score |
| Gold frequency loader | `src/evaluate.py` or `src/intake.py` | Load all annotations per letter, not just first |
| Gan category evaluator | `src/gan_frequency.py` | Convert normalized labels to Purist/Pragmatic categories |
| Gan prediction runner | `src/model_expansion.py` or `src/gan_frequency.py` | Run frequency-only prompts and write `predictions.json` |
| `Gan_direct_label` harness | `src/model_expansion.py` or focused runner | Single-call normalized-label output |
| `Gan_two_pass` harness | `src/model_expansion.py` or focused runner | Quote then normalize |
| `Gan_fs_hard` harness | `src/model_expansion.py` or focused runner | Few-shot hard cases |
| Harness routing | `src/model_expansion.py` | Register new Gan harness IDs if using model expansion |
| (Conditional) `seizure_frequency_items` schema | `configs/schema.json` | Only if F5 is run |
| (Conditional) `seizure_frequency_items_f1` scorer | `src/evaluate.py` | Only if F5 is run |

**Scoring change note:** The gold frequency loader change in Stage F1 is the single most
important implementation step. Without it, the per-letter metric cannot be computed.

---

## Benchmarks and Dissertation Claim Structure

### The benchmark and its context

| Source | Score | Method | Dataset |
|---|---|---|---|
| Gan 2026 — Qwen2.5-14B CoT(15000) | 0.788 Purist / **0.847 Pragmatic micro-F1** | Synthetic CoT fine-tuning | Clinician double-checked real-letter test set |
| Gan 2026 — MedGemma-4B CoT(15000) | 0.787 Purist / **0.858 Pragmatic micro-F1** | Synthetic CoT fine-tuning | Clinician double-checked real-letter test set |
| Fonferko-Shadrach 2024 — human IAA | 0.47 per-item | Expert annotators (consensus) | ExECTv2 synthetic letters |
| Fonferko-Shadrach 2024 — ExECTv2 | **0.66** per-item / **0.68** per-letter | Rule-based GATE pipeline | ExECTv2 synthetic letters (same data) |
| Our G2 best, 50-doc development sweep | 0.760 Purist / **0.800 Pragmatic micro-F1** | `gpt_5_5` prompted `Gan_cot_label` | Gan local synthetic subset, 50 docs |
| Our current best ExECTv2 crosswalk (GPT-4.1-mini, E3) | 0.15 per-letter / 0.125 loose | LLM extraction, single value | ExECTv2 validation split |

Gan supplies the best frequency-specific evaluation frame because it was designed around
seizure-frequency normalization, structured labels, evidence spans, unknown/no-reference
handling, seizure-free intervals, and cluster patterns. The dissertation frequency claim should
therefore lead with Gan-style Pragmatic/Purist micro-F1.

ExECTv2 remains a crosswalk benchmark. Its rule-based pipeline, designed specifically for that
dataset with domain-expert rules, achieves **0.66 per-item** and **0.68 per-letter**. This is
still valuable for showing continuity with the broader extraction evaluation, but it should not
be treated as the primary seizure-frequency benchmark now that Gan is available.

### Dissertation claim templates

**If G4 Pragmatic micro-F1 ≥ 0.85 on the local Gan subset:**
> "Using [best approach], our system achieved Gan-style Pragmatic seizure-frequency micro-F1
> of [X] on the released synthetic Gan subset, meeting the performance range reported by
> Gan et al. for scaled synthetic CoT fine-tuning on their independent real-letter test set
> (0.847-0.858). Because our evaluation subset is synthetic rather than the paper's
> clinician double-checked real test set, this result should be interpreted as a benchmark-aligned
> synthetic-data comparison rather than a direct replication."

**If G4 Pragmatic micro-F1 is 0.75-0.84:**
> "Our best system achieved Gan-style Pragmatic seizure-frequency micro-F1 of [X] on the
> released synthetic subset. This is below Gan et al.'s scaled fine-tuned target of 0.847-0.858
> but substantially more benchmark-aligned than exact-string frequency scoring, and error
> analysis shows the residual gap is concentrated in [clusters / seizure-free intervals /
> unknown vs no-reference / range normalization]."

**If G4 Pragmatic micro-F1 < 0.75:**
> "Seizure-frequency extraction remains difficult even under Gan's structured label scheme.
> Pragmatic micro-F1 of [X] falls well below the 0.847-0.858 scaled fine-tuning target,
> suggesting that prompt-only extraction is insufficient for this task without either
> task-specific fine-tuning, stronger normalization, or multi-pass evidence-grounded reasoning."

**ExECTv2 crosswalk addendum if applicable:**
> "On the ExECTv2 validation crosswalk, the same approach achieved per-letter seizure-frequency
> accuracy of [Y] against the ExECTv2 rule-based benchmark of 0.68. This lower/higher transfer
> result reflects differences between Gan's single-label normalized frequency task and
> ExECTv2's multi-mention annotation scheme."

All outcomes produce a valid, benchmarked dissertation claim as long as the metric and dataset
are named precisely.

### Updated comparison table structure

| System | Dataset | Pragmatic micro-F1 | Purist micro-F1 | ExECTv2 per-letter | Notes |
|---|---|---:|---:|---:|---|
| Gan 2026 Qwen2.5-14B CoT(15000) | real test set | 0.847 | 0.788 | — | Published target |
| Gan 2026 MedGemma-4B CoT(15000) | real test set | 0.858 | 0.787 | — | Published target |
| G2 `gpt_5_5` + `Gan_cot_label` | Gan local synthetic subset, 50-doc dev | 0.800 | 0.760 | — | Promote to G3 |
| G2 `gpt_5_5` + `Gan_direct_label` | Gan local synthetic subset, 50-doc dev | 0.760 | 0.760 | — | Strong exact-label challenger |
| G2 `claude_sonnet_4_6` + `Gan_direct_label` | Gan local synthetic subset, 50-doc dev | 0.760 | 0.760 | — | Lower-cost challenger |
| ExECTv2 rule-based | ExECTv2 | — | — | 0.68 | Crosswalk target |
| E3 H0 GPT-4.1-mini existing | ExECTv2 validation | — | — | 0.15 | Current crosswalk baseline |
| [best G4 system] | Gan local synthetic subset | TBD | TBD | optional | Main frequency result |

---

## Cost Estimate

| Stage | Model calls | Est. cost |
|---|---|---|
| F0/F1 ExECTv2 crosswalk audit/rescore | 0 | $0 |
| G0 Gan audit/metric lock | 0 | $0 |
| G1 runner implementation smoke | 5-20 | <$1 |
| G2 Gan model × prompt sweep, completed 50-doc run | 750 | ~$4.54 |
| G2 Gan model × prompt sweep, original 150-doc design | 1,800 | model-dependent |
| G3 focused prompt iteration, 50-doc controlled subset | 150-250 | model-dependent |
| G3 focused prompt iteration, 150-doc expansion | 450-900 | model-dependent |
| G4 full local Gan subset (1 best condition × 1,500 docs) | 1,500-3,000 | model-dependent |
| F5 ExECTv2 per-item crosswalk | 0-80 | $0 if re-scoring existing list outputs |

Cost is now dominated by Gan full-subset model calls. Run G2 on a deterministic development
subset first, and only promote one or two conditions to G4.

---

## Priority and Sequence

```
F0/F1 ExECTv2 crosswalk audit + rescore (done / zero cost)
  → G0 Gan metric lock + local subset audit (done / zero cost)
      → G1 Gan prediction runner (done / stub-verified)
          → G2 Gan model × prompt sweep (done on 50 docs; best = gpt_5_5 + Gan_cot_label)
              → G3 Gan hard-case prompt development (next)
                  → G4 Gan full-subset benchmark run
                      → F5 ExECTv2 per-item crosswalk (conditional)
```

The benchmark target is now explicit: **Gan Pragmatic micro-F1 >= 0.85**. ExECTv2 per-letter
frequency remains a secondary transfer/crosswalk metric rather than the main optimization target.
