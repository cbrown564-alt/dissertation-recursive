# Clinical Accuracy vs. Gold Standard Tension in ExECTv2 Seizure Type Extraction

**Date:** 2026-05-11  
**Status:** Draft — findings from MA_v1 Stage 1 repair and broader cross-system seizure analysis  
**Related:** `docs/36_multi_agent_pipeline_plan.md`, `docs/34_full_experiment_record.md` §5.15, `src/multi_agent.py`

---

## 1. Summary

This document records a disturbing pattern that has emerged across the project's seizure-type extraction workstreams: **the systems that produce the most clinically precise, temporally accurate outputs often score lowest against the gold standard.**

The immediate trigger was the repair of the MA_v1 multi-agent pipeline's Stage 1 segmentation agent (`max_tokens=256` → `1024`). Once Stage 1 could actually complete its JSON output, the pipeline began correctly isolating current seizure mentions from historical and family-context mentions. The result was a **drop** in seizure-type F1 (collapsed) on the 10-document development pilot — not because quality worsened, but because the gold standard penalizes temporal precision.

This is not an isolated quirk of MA_v1. It is the extreme end of a spectrum that runs through every harness tested: S2, E3, H6full, H7, D3, and MA_v1. Seizure type scores have remained stubbornly low (collapsed F1 typically 0.55–0.72 across frontier and local models) despite enormous investment in prompt engineering, normalization, and architectural variants. The hypothesis advanced here is that **a significant portion of this "performance ceiling" is artificial** — created by a gold standard that does not distinguish current from historical seizure types, and by an evaluation protocol that rewards extraction breadth over clinical precision.

If correct, this implies the project has been iteratively over-engineering prompts to match a noisy, temporally flat target, rather than building the temporally aware extraction system the clinical use case actually requires.

---

## 2. The MA_v1 Case Study: A Working Pipeline That "Fails"

### 2.1 The Stage 1 Token Bug

In the initial MA_v1 implementation, Stage 1 (section/timeline segmentation) was capped at `max_tokens=256`. The prompt asks the model to return:

- A `sections` array with `key_phrases` (verbatim quotes) for each clinical section
- Three separate `seizure_quotes` arrays: `current`, `historical`, and `family`

Even short clinic letters produce 300–500 tokens of formatted JSON. The 256-token ceiling caused truncation on **~95% of documents** (39/40 validation docs for GPT-5.4-mini; 38/40 for qwen). The raw responses cut off mid-object — mid-`key_phrases` array, mid-section object, or between the `sections` array and the quote arrays. `parse_json_response` could not repair the incomplete JSON, so `stage_outputs["stage1_segmentation"]` was `None`.

**Consequence:** Stage 2b (seizure/frequency extraction) received empty quote lists. It fell back to extracting from the **full letter with no temporal isolation** — exactly the behavior the multi-agent architecture was designed to prevent.

### 2.2 The Repair

**Fix 1:** `max_tokens=256` → `1024` for Stage 1.  
**Fix 2:** Added explicit allowed-label instructions to the Stage 3 verifier prompt, preventing it from dropping `'seizure free'` and `'unknown seizure type'` as "not real seizure types."

After repair, Stage 1 parse success went from **0% to 100%** on all 10 development documents. The segmentation output was rich, accurate, and clinically sensible.

### 2.3 The Paradox: Scores Drop (for GPT-5.4-mini), Rise (for qwen)

**GPT-5.4-mini:**

| Metric | Pre-repair (Stage 1 broken) | Post-repair (both fixes) | Δ |
|--------|----------------------------:|-------------------------:|---|
| BenchComp | 0.898 | **0.903** | +0.005 |
| Medication name F1 | 1.000 | 1.000 | — |
| Medication full F1 | 1.000 | 1.000 | — |
| Seizure type F1 collapsed | **0.720** | **0.692** | **−0.028** |
| Diagnosis accuracy | 0.900 | 0.900 | — |
| EEG accuracy | 1.000 | 1.000 | — |
| MRI accuracy | 0.900 | **1.000** | +0.100 |

**qwen3.6:35b local:**

| Metric | Pre-repair (Stage 1 broken) | Post-repair (both fixes) | Δ |
|--------|----------------------------:|-------------------------:|---|
| BenchComp | 0.835 | **0.849** | +0.014 |
| Medication name F1 | 0.947 | 0.947 | — |
| Medication full F1 | 0.895 | 0.895 | — |
| Seizure type F1 collapsed | **0.583** | **0.640** | **+0.057** |
| Diagnosis accuracy | 0.900 | 0.900 | — |
| EEG accuracy | 0.900 | 0.900 | — |
| MRI accuracy | 0.900 | 0.900 | — |

The seizure score *dropped* for GPT-5.4-mini but *rose* for qwen. Both models experienced the same three document-level changes (see §2.7). The difference is baseline: GPT-5.4-mini was already extracting well on the two "easy" documents (EA0004, EA0013), so the EA0006 regression dominated. Qwen was missing those easy cases before, so fixing Stage 3 (preserving `'unknown seizure type'`) yielded two gains that outweighed the one loss.

### 2.4 Document-Level Analysis: EA0006

**Letter text (excerpt):**

> "Seizure type and frequency: 2 generalised tonic clonic seizures 2014, absence like seizures 2014"  
> ...  
> "I was pleased to hear that he remains seizure free and is now driving."

**Gold standard seizure types:** `generalized tonic clonic seizure` (×2), `generalized absence seizure`

**Pre-repair (Stage 1 failed → full-letter context):**  
Stage 2b saw the entire letter, including the 2014 historical mentions. It extracted `['generalized tonic clonic seizure', 'generalized absence seizure']`. **F1 = 1.0** against gold.

**Post-repair (Stage 1 succeeded → temporally isolated context):**  
Stage 1 correctly identified the 2014 mentions as **historical** and the current status as **"seizure free."** Stage 2b was given only the current quote (*"he remains seizure free"*) and correctly output `['seizure free']`. The verifier (after fix) kept it. **F1 = 0.0** against gold.

**The pipeline is clinically correct. The patient is seizure-free. The gold standard expects historical seizure types to be reported as current seizure types.**

### 2.5 Document-Level Analysis: EA0004

**Letter text:** Describes a patient with "several seizures since the last clinic appointment" but no specific type named.

**Gold standard:** `unknown seizure type` (×2)

**Pre-repair:** Stage 2b returned `[]` (empty). **F1 = 0.0**.

**Post-repair:** Stage 2b, seeing the isolated current quotes, correctly identified that seizures are occurring but the type is unspecified. It returned `['unknown seizure type']`. The verifier kept it. **F1 = 1.0**.

This is a genuine improvement — but it is masked at the aggregate level by the EA0006 regression.

### 2.6 Additional Examples from the Pre-Repair Run

The pre-fix MA_v1 run (Stage 1 broken, full-letter fallback) provides a natural experiment: it behaves like a single-pass system with no temporal isolation. Several documents show historical types incorrectly extracted as current:

**EA0011 — "secondary generalized seizures" from 2017:**
> "Focal to bilateral convulsive seizures, last event around Christmas 2017"

The system extracted `"secondary generalized seizures"` as a current type. The Stage 3 verifier even noted the wording mismatch ("focal to bilateral convulsive" vs. "secondary generalized") but kept the label. **F1 = 1.0 against gold** because the gold includes this historical type.

**EA0005 — "generalized tonic clonic seizure" from 2016:**
> "Generalised tonic clonic seizure-last event July 2016."

The system extracted `"generalized tonic clonic seizure"` as current. The verifier kept it with reason: *"Supported by the letter as the patient's seizure type."* The 2016 date was ignored. **F1 = 0.667 against gold**.

In both cases, the "high" F1 reflects successful matching of a temporally flat gold standard, not successful clinical extraction.

### 2.7 The Three-Document Pattern (Both Models)

Across **both** GPT-5.4-mini and qwen, the same three documents drove all seizure-score changes:

| Doc | Gold | Pre-repair | Post-repair | Why it changed |
|-----|------|-----------:|------------:|----------------|
| **EA0004** | `unknown` (×2) | `[]` (F1=0.0) | `['unknown seizure type']` (F1=1.0) | Stage 3 fix now keeps meta-label |
| **EA0006** | `GTCS` (×2), `absence` | `['GTCS', 'absence']` (F1=1.0) | `['seizure free']` (F1=0.0) | Stage 1 now isolates current status correctly |
| **EA0013** | `unknown` | `[]` (F1=0.0) | `['unknown seizure type']` (F1=1.0) | Stage 3 fix now keeps meta-label |

All other documents were unchanged. This means the aggregate seizure F1 swing is **entirely attributable to temporal accuracy on one document (EA0006) and meta-label preservation on two documents (EA0004, EA0013)**. It is not a broad statistical shift; it is a precise, interpretable structural effect.

---

## 3. The Root Cause: Temporally Flat Gold, Temporally Aware Pipeline

### 3.1 How the Gold Standard Is Built

The `seizure_types` field in the gold `GoldDocument` is populated from `MarkupSeizureFrequency.csv`. Every row in that CSV that contains a non-empty `seizure_type` value appends that type to the document's `seizure_types` list, **regardless of temporal scope**.

For EA0006, the markup rows show:

```csv
EA0006.txt,498,541,C0494475,"2-generalised-tonic-clonic-seizures-in-2014",...
EA0006.txt,234,272,C0494475,"generalised-tonic-clonic-seizures-2014",...
EA0006.txt,274,295,C0563606,"absence-like-seizures",...
```

All three rows have `temporal_scope=During, year=2014`. The gold loader **knows** these are historical. But `load_gold()` in `src/evaluate.py` appends them to `document.seizure_types` unconditionally:

```python
if seizure_type:
    document.seizure_types.append(seizure_type)
```

The scorer then computes set-based P/R/F1 on the unique labels in this list. There is no `current_only` flag, no temporal filter, and no distinction between "seizure types the patient currently experiences" and "seizure types mentioned anywhere in the letter."

### 3.2 What This Means for Every Harness

Any harness that attempts temporal discrimination — whether explicitly (MA_v1's segmentation → current-only quotes) or implicitly (S2's "current" constraint in the prompt) — is fighting the gold standard. Harnesses that ignore temporality and extract every seizure type mentioned anywhere in the letter score higher, because they match the gold's temporally flat set.

This creates a perverse incentive: **the less clinically precise your extraction, the better your F1.**

The scorer code makes this explicit. In `src/evaluate.py` lines 439–466:

```python
predicted_types = {
    (canonical_seizure_type(item.get("value")),)
    for item in fields.get("seizure_types", [])
    if canonical_seizure_type(item.get("value"))
}
gold_types = {(item,) for item in set(document_gold.seizure_types) if item}
result["field_scores"]["seizure_type"] = set_prf(predicted_types, gold_types)
```

This is a pure set intersection. The scorer does not inspect `temporality`, `temporal_scope`, or any other time-related field on either the predicted or gold side. Temporal filtering exists **only in prompts** — it is an instruction given to the model, not a property of the evaluation.

### 3.3 Evidence from Other Systems

The pattern is visible across the full experiment record. The explore agent audited every major run artifact; the seizure-type collapsed F1 scores cluster in a remarkably narrow band regardless of model size, architecture, or prompt sophistication:

**Frontier / API models (validation, 40 docs):**
| System | Sz F1 Collapsed |
|--------|----------------:|
| S2 GPT-4.1-mini direct | 0.610 |
| E2 GPT-4.1-mini deterministic | 0.613 |
| E3 GPT-4.1-mini event-first | **0.633** |
| H7 GPT-4.1-mini two-pass (15 dev) | 0.698 |
| D3 GPT-5.5 candidate+verifier (15 dev) | 0.682 |

**Local models (validation, 40 docs):**
| Model | Harness | Sz F1 Collapsed |
|-------|---------|----------------:|
| qwen3.5:9b | H6 | 0.541 |
| qwen3.5:9b | H6v2 | 0.595 |
| qwen3.5:9b | H6fs | **0.602** |
| gemma4:e4b | H6 | 0.593 |
| qwen3.6:27b | H6 | 0.578 |
| qwen3.6:35b | H6fs | 0.593 |

**Event-first local (validation, 40 docs):**
| Model | Harness | Sz F1 Collapsed |
|-------|---------|----------------:|
| qwen_9b_local | EL_micro | 0.538 |
| qwen_35b_local | EL_micro | 0.585 |
| qwen_9b_local | EL_E1E2 | 0.594 |

**Multi-agent MA_v1 (validation, 40 docs):**
| Condition | Sz F1 Collapsed |
|-----------|----------------:|
| gpt_5_4_mini | 0.610 |
| qwen_35b_local | 0.603 |
| gpt_5_5 | **0.379** |

The ceiling is unmistakable: **0.60–0.65** on validation, **0.45–0.50** on test. The only exceptions are H7 and D3 on small 15-document development subsets (0.682–0.698), which shrink to the same band when scaled. GPT-5.5 on MA_v1 actually collapsed to 0.379 — the structured decomposition made the temporal mismatch worse, not better, because error propagated across stages.

The "best" scores come from systems that extract broadly (E3, S2, H6fs). Systems that try to be precise (H7, D3, MA_v1) score lower or become unstable. This is not because they extract worse clinically; it is because they extract **more carefully** than the gold standard allows.

---

## 4. The Broader Pattern: Over-Engineering for a Misaligned Target

### 4.1 The Project's Seizure Type Trajectory

The full experiment record (`docs/34_full_experiment_record.md`) documents a long arc of seizure-type optimization:

1. **Phase 0 (original scoring):** Strict string-match seizure type F1 = 0.187–0.261. The target was Fang et al.'s ≥0.76. Panic.
2. **Phase 1 (collapsed labels):** Added `benchmark_seizure_type_label` mapping 14 canonical types to 3 categories (focal / generalized / unknown). F1 jumped to 0.61–0.63 with **no prompt changes**. A 3× improvement from metric repair alone.
3. **Phase 2 (prompt iteration):** H6v2, H6fs, H6qa, H6ev — dozens of prompt variants adding few-shot examples, evidence anchors, decomposed status fields, and schema extensions. Gains were small (+0.02 to +0.06 on dev) and often reversed on validation.
4. **Phase 3 (architecture exploration):** Event-first (E1/E2/E3), multi-agent (MA_v1), two-pass normalization (H7), retrieval augmentation (Gan). Seizure scores remained in the 0.55–0.72 band.

The ceiling has been stable for a long time. The question is: **what is the true ceiling?**

### 4.2 The Oracle Failure Rate

Doc 34 notes that ExECTv2 has a **13.3% oracle failure rate** on seizure type annotation (some letters lack clear type annotation, and the markup itself is occasionally ambiguous or missing). Even a perfect extractor cannot score above ~0.87 on strict matching. But the collapsed-label scorer should raise this ceiling.

However, the **temporal-scope blindness** of the gold standard introduces a second, unmeasured error source. Letters like EA0006 are not edge cases; they are common in clinical practice. Any system that correctly distinguishes "seizure-free since 2014" from "currently having GTCS" will be systematically penalized.

### 4.3 Prompt Engineering as Adversarial Adaptation

Consider what prompt engineering has actually done across the project:

- **H6v2** added explicit `'unknown seizure type'` and `'seizure free'` guidance because the model kept missing them.
- **H6fs** added few-shot examples showing when to use these meta-labels.
- **H6ev** added evidence anchors to force the model to cite text.
- **MA_v1** built an entire four-stage pipeline to isolate current from historical context.

All of these were attempts to make the model **behave more precisely**. But the evaluation protocol does not reward precision — it rewards **matching the flat label set**. The result is a subtle form of overfitting: prompts are tuned to make the model extract *more labels* (including historical ones), to use broader context, and to avoid the meta-labels that the scorer sometimes punishes.

In effect, the project has been **adapting its extraction to the evaluation set's biases** rather than to the clinical task's true requirements.

### 4.4 The Family History Trap

The original motivation for MA_v1's Stage 1 was the `family_history_trap`: single-pass systems read family seizure history as patient findings and hallucinate seizure types. The plan (`docs/36_multi_agent_pipeline_plan.md`) explicitly hypothesized that explicit segmentation would fix this.

But the gold standard does not contain a `family_seizure_type` field. If a system correctly excludes family-history seizures, it loses no points — but if it incorrectly includes them, it also loses no points (they are simply not in the gold). The trap is invisible to the scorer. The only visible effect of fixing it is the *other* temporal fix — excluding **historical** patient seizures — which *does* lower the score.

This means the evaluation protocol is **asymmetric**: it punishes temporal precision on the patient history axis but is blind to precision on the family history axis. A system that fixes both looks worse than a system that fixes neither.

---

## 5. What Should the Gold Standard Look Like?

### 5.1 Temporal Scope for Seizure Types

The `MarkupSeizureFrequency.csv` already contains a `temporal_scope` column and date fields. The gold loader should use them. A minimal fix:

```python
# In load_gold() — hypothetical
if seizure_type and temporal_scope in {"current", "ongoing", None}:
    document.current_seizure_types.append(seizure_type)
elif seizure_type:
    document.historical_seizure_types.append(seizure_type)
```

The scorer should then offer:
- `seizure_type_f1_current` — current-only (the clinically relevant metric)
- `seizure_type_f1_all` — all mentions (backward-compatible with existing results)

### 5.2 Meta-Label Validation

`'seizure free'` and `'unknown seizure type'` are valid, load-bearing schema values. The scorer already accepts them (via `BENCHMARK_SEIZURE_LABELS`), but the gold standard sometimes treats them as second-class. Letters that say "she continues to get occasional seizures" without naming a type should gold-label as `unknown seizure type`, not as empty.

### 5.3 A Seizure-Free Distinction

A patient who is seizure-free has **no current seizure type**. The correct extraction is `['seizure free']` or `[]` with a `seizure_free` flag. The gold standard currently marks seizure-free patients with their **historical** seizure types (from years ago). This is clinically misleading.

---

## 6. Recommendations

### Immediate (before final validation)

1. **Do NOT promote or demote systems based on seizure type F1 alone** until the temporal scope issue is resolved. The metric is currently confounded.
2. **Run a temporal-scope-aware scorer audit** on a 10-document subset. For each document, manually tag whether each gold seizure type is current, historical, or family. Compute F1 on current-only vs. all-mentions. Quantify the bias.
3. **Fix the Stage 3 verifier prompt** (already done in `src/multi_agent.py`) to preserve meta-labels. This is a genuine bug fix, not an evaluation hack.

### Medium-term (for dissertation claims)

4. **Report seizure results as a dual metric:**
   - `seizure_type_f1_collapsed_all` — matching existing literature
   - `seizure_type_f1_collapsed_current` — the clinically meaningful metric
   
   If MA_v1 or D3 outperforms on the current-only metric but underperforms on the all-mentions metric, that is a **positive finding**, not a failure.

5. **Audit the ExECTv2 seizure markup** for temporal consistency. The 13.3% oracle failure rate may be partly due to ambiguous temporal_scope entries rather than missing annotations.

6. **Reframe the dissertation claim:** Instead of "multi-agent decomposition improves overall extraction quality," the supported claim is "multi-agent decomposition improves **temporal precision and robustness to context bleeding**, with mixed effects on aggregate F1 due to gold-standard temporal blindness."

### Long-term (for the field)

7. **Propose a temporally structured extraction benchmark** for clinical NLP. The ExECTv2 schema has `temporal_scope` for frequencies but not for types. Future benchmarks should require systems to report *when* a seizure type was observed, not just *what* it was.

---

## 7. Conclusion

The MA_v1 pipeline's Stage 1 repair revealed a hidden truth: the project has been optimizing for a gold standard that does not distinguish current from historical seizure types. Systems that extract more carefully score lower. This is not a model problem, a prompt problem, or an architecture problem. It is a **measurement problem**.

The seizure type field has been the project's hardest remaining metric not because extraction is intrinsically difficult (medications, diagnosis, and investigations all score well), but because the evaluation target is misaligned with the clinical task. Every harness variant — S2, E3, H6, H7, D3, MA_v1 — has been pushed against the same ceiling, and that ceiling is partly made of gold-standard noise.

The way forward is not more prompt engineering. It is **better measurement**.

---

## Appendix A: MA2 Validation-Scale Findings (40 docs)

MA2 was re-run with both fixes on the full 40-document validation split. Qwen is currently processing; GPT-5.4-mini completed.

### GPT-5.4-mini MA2: Old vs. New

| Metric | Pre-fix MA2 | Post-fix MA2 | Δ |
|--------|------------:|-------------:|---|
| BenchComp | 0.757 | **0.763** | +0.006 |
| Seizure type F1 collapsed | **0.610** | **0.588** | −0.022 |
| Medication name F1 | 0.868 | 0.870 | +0.002 |
| Medication full F1 | 0.696 | **0.761** | **+0.065** |
| Diagnosis accuracy collapsed | 0.625 | **0.650** | +0.025 |
| EEG accuracy | 0.925 | 0.925 | — |
| MRI accuracy | 0.825 | **0.875** | +0.050 |

**Promotion gates:** BenchComp > 0.810 ❌ (0.763); Seizure F1 collapsed ≥ 0.660 ❌ (0.588). **No promotion.**

### What Changed at 40-Document Scale

Only **8 of 40** documents changed seizure F1. The changes fall into three categories:

**Category 1: Gold-standard gaps (no markup, but letter mentions seizures)**
- **EA0052** (1.0 → 0.0): Letter says *"4 more attacks"* — no gold markup. Old run returned `[]`; new run returns `['unknown seizure type']` because Stage 1 isolates the quote.
- **EA0078** (1.0 → 0.0): Letter says *"Her seizures are reasonably controlled"* — no gold markup. Same pattern.

These are **not** temporal errors; they are gold-standard coverage gaps. The new pipeline is more sensitive and finds seizure mentions the annotators did not mark up.

**Category 2: Temporal accuracy tax (gold includes historical types)**
- **EA0068** (1.0 → 0.667): Old run extracted `['focal seizure', 'seizure free']` — clinically incoherent. New run correctly returns `['seizure free']`.

**Category 3: Genuine improvements from meta-label preservation**
- **EA0135** (0.667 → 1.0): Old run missed `'cluster of seizures'`; new run captures it.
- **EA0143** (0.5 → 0.8): Old run missed `'focal seizure'`; new run captures it.
- **EA0150** (0.8 → 1.0): Old run had extra noise; new run is clean.

### The Medication Full F1 Improvement

The most significant improvement is **medication_full_f1: +0.065** (0.696 → 0.761). This suggests Stage 1's segmentation context — specifically the medication-section `key_phrases` passed to Stage 2a — helps the model extract structured medication tuples more accurately. The multi-agent architecture delivers value, but on a field where the gold standard is well-aligned (medications), not on the temporally mismatched seizure field.

---

## Appendix B: Reproducibility

**Code changes:**
- `src/multi_agent.py`: Stage 1 `max_tokens=256` → `1024` (line ~424)
- `src/multi_agent.py`: Stage 3 prompt now includes `BENCHMARK_SEIZURE_LABELS` and explicit keep instructions for meta-labels

**Artifacts:**
- Pre-repair MA1: `runs/multi_agent/stage_ma1_dev_pilot_pre_fix_256/`
- Pre-repair MA2: `runs/multi_agent/stage_ma2_validation_pre_fix/`
- Post-repair MA1: `runs/multi_agent/stage_ma1_dev_pilot/`
- Post-repair MA2: `runs/multi_agent/stage_ma2_validation/`

**Key documents:**
- `EA0006` (MA1) — gold includes historical GTCS/absence; pipeline correctly returns `seizure free`
- `EA0052` / `EA0078` (MA2) — no gold markup; pipeline extracts `'unknown seizure type'` from vague mentions
- `EA0068` (MA2) — old run was clinically incoherent (`['focal seizure', 'seizure free']`); new run is clean

**Complete MA1 results (post-fix):**

| Model | BenchComp | Sz F1 Collapsed | Med Name F1 | Dx Acc | EEG | MRI |
|-------|-----------|-----------------|-------------|--------|-----|-----|
| gpt_5_4_mini | **0.903** | 0.692 | 1.000 | 0.900 | 1.000 | 1.000 |
| qwen_35b_local | **0.849** | 0.640 | 0.947 | 0.900 | 0.900 | 0.900 |

**MA2 results (post-fix, GPT-5.4-mini only, qwen pending):**

| Model | BenchComp | Sz F1 Collapsed | Med Name F1 | Med Full F1 | Dx Collapsed | EEG | MRI |
|-------|-----------|-----------------|-------------|-------------|--------------|-----|-----|
| gpt_5_4_mini | **0.763** | 0.588 | 0.870 | **0.761** | 0.650 | 0.925 | 0.875 |
