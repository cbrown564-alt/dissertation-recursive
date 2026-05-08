# Seizure Frequency Improvement Workstream

**Date:** 2026-05-08  
**Benchmark:** Fonferko-Shadrach et al. 2024 (J Biomed Semantics 15:17) — ExECTv2 achieves
seizure frequency **per-item F1 = 0.66**, per-letter F1 = 0.68, using the same ExECTv2 dataset.
Human inter-annotator agreement for seizure frequency was only **0.47** — the lowest of any
annotated entity, lower than even complex fields like Patient History (0.57).  
**Goal:** Reach or exceed per-letter F1 = 0.68 on the validation split using LLM-based extraction.

---

## Critical Context from Fonferko-Shadrach 2024

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

**Option 2 — Per-item multi-annotation (harder, matches primary benchmark)**
- Score: extract all frequency mentions; score F1 across all gold annotations.
- Matches the paper's per-item F1 (0.66 target).
- Requires schema and pipeline change: `seizure_frequencies` list, not a single value.
- Event-first (E3) is the natural architecture: each frequency event becomes one item.
- **Implementation:** New `seizure_frequency_items` field; `frequency_items_f1` scorer.

**Option 3 — Keep current loose_accuracy (incomparable, not recommended)**
- Retains `current_seizure_frequency_loose_accuracy` as-is.
- Cannot be directly compared to the 0.66/0.68 benchmark.
- Only defensible if a crosswalk between the two metrics is documented.

**Recommendation:** Implement Option 1 first (low cost, immediate benchmark comparability),
then Option 2 if F3 shows per-letter accuracy well above 0.68 (meaning per-item is the
remaining gap).

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
- If existing best system already reaches ≥ 0.50 per-letter → the model capability gap is
  smaller than expected; move directly to prompt engineering (Stage F3).
- If existing best system is 0.20–0.49 → there is substantial headroom; run model sweep (F2).
- If existing best system is < 0.20 → the issue is likely gold data loading, not model capability;
  audit the gold loader before F2.

---

## Stage F2: Model × Pipeline Sweep

**Purpose:** Establish whether larger frontier models and/or E3's constrained LLM aggregation
materially improve per-letter frequency accuracy. GPT-4.1-mini has not been tested against
larger models on this specific field; the human IAA ceiling of 0.47 is already exceeded by
ExECTv2's rules, so stronger models should do better.

**Design:**

| Axis | Values |
|---|---|
| Models | `gpt_4_1_mini` (baseline), `gpt_5_5`, `claude_sonnet_4_6` |
| Pipelines | `S2` (direct extraction), `E3` (event-first + LLM aggregation) |
| Harness | `H0_strict_canonical` |
| Split | Development (15 docs) |
| Repeats | 1 |
| Primary metric | `current_seizure_frequency_per_letter_accuracy` (new) |
| Secondary | `current_seizure_frequency_loose_accuracy` (old, for continuity) |

**4 new conditions** (2 existing GPT-4.1-mini conditions are re-scored from existing runs):
- `gpt_5_5` × S2
- `gpt_5_5` × E3
- `claude_sonnet_4_6` × S2
- `claude_sonnet_4_6` × E3

**Why E3 specifically:** E3's constrained LLM aggregation step reviews all frequency events and
selects the most relevant one. This is structurally better suited to multi-mention letters than
S2's direct single-value extraction.

**Outputs:**
- `runs/frequency_workstream/stage_f2/comparison_table.csv`
  (model, pipeline, freq_per_letter, freq_loose, sz_type_collapsed, med_name, cost_per_doc)
- `runs/frequency_workstream/stage_f2/promotion_decision.md`

**Decision rule:**
- Promote the best model × pipeline to Stage F3 if per-letter accuracy ≥ 0.35 on dev.
- If GPT-4.1-mini matches larger models → all subsequent stages use GPT-4.1-mini (cost saving).

---

## Stage F3: Frequency-Focused Prompt Development

**Purpose:** Design prompts specifically targeting frequency extraction. Run on the best model
from Stage F2 across 15 dev docs. The key hypothesis is that the generic canonical extraction
prompt allocates insufficient "attention" to frequency — a dedicated prompt should help.

### F3-A: Dedicated Frequency Harness (`H_freq`)

Standalone prompt that extracts *only* seizure frequency (not embedded in the full canonical
schema prompt). Removes competition with other fields.

```
## Task
Extract ALL mentions of seizure frequency from this epilepsy clinic letter.
Frequency includes: current rate, historical rate, seizure-free periods, and changes since
the last visit.

## Output format
Return a JSON array. For each mention:
{"frequency": "<count> per <period> | seizure-free | <qualitative>",
 "seizure_type": "<type if specified> | all",
 "temporal": "current | historical | change",
 "quote": "<verbatim span from letter>"}

Return [] if no frequency information is stated.

## Examples
"2-3 GTCS per month" → {"frequency": "2-3 per month", "seizure_type": "GTCS", "temporal": "current", "quote": "2-3 GTCS per month"}
"remains seizure-free" → {"frequency": "seizure-free", "seizure_type": "all", "temporal": "current", "quote": "remains seizure-free"}
"fewer seizures since last clinic" → {"frequency": "reduced", "seizure_type": "all", "temporal": "change", "quote": "fewer seizures since last clinic"}

## Clinical letter
{document_text}
```

Scoring: per-letter binary — any extracted item that loose-matches any gold annotation → 1.

### F3-B: Two-Pass Frequency Harness (`H7_freq`)

Adapts H7 for frequency extraction specifically. Separates "find the text" from "parse the text."

- **Pass 1 (extract)**: Quote every sentence or clause mentioning seizure frequency, rate,
  seizure-free status, or frequency change. Return verbatim strings only.
- **Pass 2 (normalize)**: Given the quoted text, normalize each mention to canonical form.

This worked well for seizure type (H7: 0.698 vs H0: 0.524 strict). The same principle applies
here — local models and weaker frontier models can find the text even when they fail to
normalize it.

### F3-C: Chain-of-Thought Prefix (`H_cot_freq`)

Add explicit reasoning steps before JSON output:

```
Step 1: Find all sentences that mention how often seizures occur, seizure rate,
        seizure-free periods, or frequency changes.
Step 2: For each, identify the seizure type (or "all"), whether it is current or historical,
        and the count and period if stated.
Step 3: Output the results as JSON.
```

### F3-D: Few-Shot with Hard Cases (`H_fs_freq`)

Add 5 annotated examples covering the hardest patterns:

```
## Examples

"He continues to have 1-2 focal seizures per week"
→ current, focal, 1-2/week

"She has been seizure-free for 6 months"
→ current, all, seizure-free (last seizure 6 months ago counts as seizure-free)

"Seizure frequency has reduced since adding lamotrigine, from 4/month to 1-2/month"
→ change + current; extract the most recent (1-2/month)

"His GTCS are well controlled but he continues to have 3-4 absence seizures per day"
→ two mentions: GTCS (controlled, seizure-free equivalent) and absences (3-4/day)

"Frequency unchanged since last appointment at approximately weekly"
→ current, all, ~1/week
```

### F3 Evaluation Design

| Condition | Harness | Model | Calls/doc |
|---|---|---|---|
| F3-A | H_freq | best from F2 | 1 |
| F3-B | H7_freq | best from F2 | 2 |
| F3-C | H_cot_freq | best from F2 | 1 |
| F3-D | H_fs_freq | best from F2 | 1 |
| Baseline | H0 | GPT-4.1-mini (re-scored) | 1 |

**Split:** Development (15 docs), 1 repeat.  
**Primary metric:** `current_seizure_frequency_per_letter_accuracy`.  
**Decision rule:** Promote the highest per-letter accuracy condition to Stage F4.

**Outputs:**
- `runs/frequency_workstream/stage_f3/comparison_table.csv`
- `runs/frequency_workstream/stage_f3/promotion_decision.md`

---

## Stage F4: Validation-Scale Run

**Purpose:** Formal evaluation of the best Stage F2+F3 combination on 40 validation documents.
These are the dissertation numbers.

**Design:**

| Item | Value |
|---|---|
| System | Best model × pipeline × harness from F2/F3 |
| Split | Validation (40 docs) |
| Repeats | 1 |
| Primary metric | `current_seizure_frequency_per_letter_accuracy` |
| Secondary | `current_seizure_frequency_loose_accuracy` (legacy continuity) |
| Benchmark target | ≥ 0.68 per-letter F1 (ExECTv2, Fonferko-Shadrach 2024) |

**Also run on test if per-letter accuracy ≥ 0.60 on validation** (within 12% of benchmark).

**Outputs:**
- `runs/frequency_workstream/stage_f4/evaluation_summary.json`
- `runs/frequency_workstream/stage_f4/comparison_vs_baseline.csv`
- Update `docs/phase3_synthesis_report.md` §4 frequency rows

---

## Stage F5: Per-Item Scoring (Conditional)

**Entry criterion:** Stage F4 per-letter accuracy ≥ 0.68 (has matched the easier benchmark).

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
| `H_freq` standalone harness | `src/model_expansion.py` | New `build_freq_prompt()` function; returns list |
| `H7_freq` two-pass harness | `src/model_expansion.py` | Two-call pipeline; log both pass outputs |
| `H_cot_freq` harness | `src/model_expansion.py` | Variant with CoT prefix |
| `H_fs_freq` harness | `src/model_expansion.py` | Variant with 5-example few-shot |
| Harness routing | `src/model_expansion.py` | Register new harness IDs |
| (Conditional) `seizure_frequency_items` schema | `configs/schema.json` | Only if F5 is run |
| (Conditional) `seizure_frequency_items_f1` scorer | `src/evaluate.py` | Only if F5 is run |

**Scoring change note:** The gold frequency loader change in Stage F1 is the single most
important implementation step. Without it, the per-letter metric cannot be computed.

---

## Benchmarks and Dissertation Claim Structure

### The benchmark and its context

| Source | Score | Method | Dataset |
|---|---|---|---|
| Fonferko-Shadrach 2024 — human IAA | 0.47 per-item | Expert annotators (consensus) | ExECTv2 synthetic letters |
| Fonferko-Shadrach 2024 — ExECTv2 | **0.66** per-item / **0.68** per-letter | Rule-based GATE pipeline | ExECTv2 synthetic letters (same data) |
| Our current best (GPT-4.1-mini, E3) | 0.125 loose (not comparable) | LLM extraction, single value | ExECTv2 validation split |

The ExECTv2 rule-based pipeline, designed specifically for this dataset with domain-expert
rules, achieves **0.66 per-item** — a score that already exceeds human annotator agreement
(0.47). This sets the practical performance ceiling for pattern-based approaches on this
data. LLMs should be competitive, but beating 0.66 per-item is not trivially expected.

The per-letter target (0.68) is more achievable — it only requires getting at least one
frequency mention right in each letter.

### Dissertation claim templates

**If F4 per-letter ≥ 0.68 (matched or beat benchmark):**
> "Using [best approach], our LLM-based system achieved per-letter seizure frequency F1 of
> [X], matching ExECTv2 (0.68) on the same dataset. Unlike the rule-based ExECTv2 pipeline,
> which was engineered specifically for this data, our approach requires no domain-expert
> rule authoring and generalizes to new letter formats without modification."

**If F4 per-letter 0.50–0.67 (below benchmark, above human IAA):**
> "Our best system achieved per-letter seizure frequency F1 of [X] — below the ExECTv2
> rule-based benchmark (0.68) but above the human inter-annotator agreement (0.47). The
> residual gap reflects the rule-based system's advantage of domain-engineered frequency
> patterns tuned to this specific dataset. Seizure frequency remains the most difficult
> extraction target, consistent with the original paper's finding that human annotators found
> it harder than any other entity."

**If F4 per-letter < 0.50 (below human IAA):**
> "Seizure frequency extraction remains unsolved at this scale. Per-letter F1 of [X] falls
> below human annotator agreement (0.47). The difficulty stems from [identified failure
> modes from F0 and F3]. ExECTv2's rule-based approach (0.68) retains an advantage due to
> hard-coded clinical frequency patterns. Future work on clinical frequency normalization
> or task-specific fine-tuning may close this gap."

All three outcomes produce a valid, benchmarked dissertation claim.

### Updated comparison table structure

| System | Freq Loose | Freq Per-Letter | Benchmark Gap | Notes |
|---|---|---|---|---|
| Human IAA (Fonferko-Shadrach) | — | 0.47 | −0.21 | Human ceiling for this task |
| ExECTv2 rule-based | — | 0.68 | 0.00 | **Target benchmark** |
| S2 H0 GPT-4.1-mini (existing) | 0.075 (val) | TBD after F1 rescore | TBD | |
| E3 H0 GPT-4.1-mini (existing) | 0.125 (val) | TBD after F1 rescore | TBD | |
| [best F4 system] | TBD | TBD | TBD | |

---

## Cost Estimate

| Stage | Model calls | Est. cost |
|---|---|---|
| F0 (gold audit) | 0 | $0 |
| F1 (rescore existing runs) | 0 | $0 |
| F2 (4 new conditions × 15 docs) | 60 | ~$2–8 |
| F3 (4 prompt conditions × 15 docs) | 60–120 (H7_freq is 2-call) | ~$1–4 |
| F4 (1 condition × 40 docs) | 40–80 | ~$1–5 |
| F5 (conditional × 40 docs) | 0 (re-score only if list already extracted) | $0 |
| **Total** | | **~$4–17** |

Cost is dominated by GPT-5.5 / Claude Sonnet 4.6 calls in F2. If F2 shows no model gain over
GPT-4.1-mini, F3–F5 run at <$2 total.

---

## Priority and Sequence

```
F0 (gold audit + scoring decision, zero cost)
  → F1 (implement per-letter scorer, rescore existing runs, zero cost)
      → F2 (model × pipeline sweep)
           → F3 (prompt engineering)
                → F4 (validation scale, dissertation numbers)
                      → F5 (per-item scoring, conditional)
```

F0 and F1 together take one coding session with no API calls. The actual benchmark target
cannot be computed until F1 is done — the gap may be smaller than 0.075–0.175 loose
accuracy implies.
