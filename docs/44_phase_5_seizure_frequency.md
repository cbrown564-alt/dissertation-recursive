# Phase 5 — Seizure Frequency Extraction: The Gan Workstream

**Date:** 2026-05-08 (G0–G3); 2026-05-09 (G4 retrieval)  
**Scope:** Dedicated seizure frequency extraction on Gan et al. 2026 synthetic subset (1,500 documents).  
**Purpose:** Establish whether retrieval-augmented frequency normalization can approach clinical utility benchmarks, given that ExECTv2 frequency is unscoreable.  
**Status:** Complete through G4-Fixed. G4-Full (1,500 docs) pending.

---

## 1. Aims & Research Questions

After all scoring fixes, ExECTv2 seizure frequency loose accuracy remained 0.075–0.175 — far below the ExECTv2 rule-based benchmark of 0.66–0.68 (Fonferko-Shadrach 2024). A dedicated workstream was opened with a **different primary benchmark**: Gan et al. 2026.

**Why Gan over ExECTv2 for frequency:**
- ExECTv2 scores multi-mention frequency extraction (all frequency mentions per letter). The 29.2% oracle failure rate (Phase 2) means even perfect extraction cannot score above ~0.71.
- Gan scores category-level extraction after normalizing a single frequency to a seizures/month rate. It was designed around frequency normalization, structured labels, evidence spans, cluster patterns, seizure-free intervals, and unknown/no-reference handling.
- Gan published Pragmatic micro-F1 targets: ≥0.85 (clinically useful 4-class grouping).

**Important caveat:** Gan's published figures (Qwen2.5-14B CoT = 0.847; MedGemma-4B CoT = 0.858) were measured on a separately produced clinician double-checked real-letter test set, not on the released synthetic subset used here.

**Primary research questions:**
1. Can frontier models achieve Pragmatic micro-F1 ≥ 0.85 on Gan frequency normalization?
2. Does retrieval augmentation (providing relevant frequency spans as highlighted context) improve normalization accuracy?
3. Do hard-case few-shot examples help or harm, given the Phase 3 finding that few-shot effects are model-specific?
4. Can local models (qwen_35b) achieve competitive frequency extraction at zero cost?

**What we knew when we started:**
- Phase 2 (Recovery) had shown ExECTv2 frequency was fundamentally constrained by annotation quality.
- Phase 3 (Local Models) had shown qwen_35b could match frontier performance on medication and seizure type.
- Phase 1 (Frontier Selection) had shown GPT-4.1-mini was cost-effective, but GPT-5.5 might be needed for harder reasoning tasks.

---

## 2. G0: Gold Audit and Metric Lock

**Artifact:** `runs/gan_frequency/audit/`

Before any model calls, the gold distribution was verified and the metric calculation locked. This discipline was explicitly adopted to prevent the ExECTv2 gold-loader-bug problem from recurring.

**What was done:**
1. Loaded 1,500 examples from `data/Gan (2026)/synthetic_data_subset_1500.json`
2. Extracted normalized labels and mapped to Purist (10-bin) and Pragmatic (4-class) categories
3. Wrote `gan_gold_labels.csv` and `gan_gold_audit.json`
4. Verified label converter on manual cases
5. Ran stub smoke tests to confirm scoring pipeline end-to-end

**Gold label distribution (Pragmatic 4-class):**

| Class | Count | Proportion |
|-------|-------|------------|
| frequent | 757 | 50.5% |
| UNK (unknown) | 264 | 17.6% |
| infrequent | 256 | 17.1% |
| NS (no seizure frequency reference) | 223 | 14.9% |

**Learning:** Locking the metric before running experiments is the right discipline. The ExECTv2 experience showed what happens when you don't.

---

## 3. G1: Prediction Harness (Stub Verification)

**Artifact:** `runs/gan_frequency/stage_g1/`

Five harnesses were built and stub-verified:
- `Gan_direct_label`: Single normalized label, no reasoning
- `Gan_cot_label`: Chain-of-thought reasoning, then label
- `Gan_evidence_label`: Label plus exact evidence quote
- `Gan_two_pass`: Quote extraction pass, then normalization pass
- `Gan_fs_hard`: Direct label with hard-case few-shot examples

Output format per document: a single normalized label string (e.g., `"2 per 5 month"`, `"seizure free for 12 month"`, `"unknown"`, `"no seizure frequency reference"`).

**Learning:** The prediction harness worked cleanly. The decision to invest in score-before-run infrastructure paid off in G2 when it made fast iteration over 12 conditions possible.

---

## 4. G2: Model × Prompt Sweep (50 docs, $4.54 total)

**Design:** 3 models × 4 harnesses = 12 conditions; 50 deterministic development docs; 1 repeat.

**Models:** GPT-4.1-mini, GPT-5.5, qwen_35b_local. (Claude Sonnet 4.6 was planned but deferred.)

**Critical infrastructure note:** GPT-5.5 had 15/150 empty-response failures due to `max_output_tokens=512` budget exhaustion — all tokens were consumed by internal reasoning before the output was produced. This depressed GPT-5.5 scores in G2 and was corrected in G4-Fixed.

**G2 results (GPT-5.5 scores depressed by token budget issue):**

| Rank | Model | Harness | Prag F1 | Pur F1 | Exact | Parse OK | Cost |
|------|-------|---------|---------|--------|-------|----------|------|
| 1 | gpt_5_5 | Gan_cot_label | **0.800** | 0.760 | 0.540 | 0.887 | $0.62 |
| 2 | gpt_5_5 | Gan_direct_label | 0.760 | 0.760 | 0.600 | 0.887 | $0.62 |
| 3 | gpt_4_1_mini | Gan_direct_label | 0.713 | 0.673 | 0.480 | 0.993 | $0.02 |
| 4 | qwen_35b_local | Gan_direct_label | 0.700 | 0.667 | 0.520 | 1.000 | $0 |
| 5 | gpt_5_5 | Gan_two_pass | 0.340 | 0.340 | 0.180 | — | $1.11 |

**Promotion decision:** `gpt_5_5` + `Gan_cot_label` → Stage G3. Exceeded the 0.75 Pragmatic micro-F1 promotion threshold.

**Learning:**
- CoT label outperforms direct label for GPT-5.5.
- Evidence label hurts (model attaches a quote but the normalization step is impaired).
- Two-pass normalization performs worst of all, suggesting the two-pass output-path parsing needs hardening.
- GPT-4.1-mini's 0.713 is surprisingly good at 2¢/50 docs.

---

## 5. G3: Hard-Case Prompt Development (50-doc controlled subset)

**Idea:** Iterate the best G2 model/harness on hard Gan patterns: clusters, ranges, seizure-free intervals, unknown frequency, no-reference cases.

**New harness:** `Gan_fs_hard` — adds five few-shot examples covering the hardest Gan categories (cluster days, seizure-free-for-N-months, sporadic unclear, no-reference, multiple seizure types).

**Result:** The hard-case few-shot prompt **reduced** Pragmatic micro-F1 from 0.80 to 0.64 on the controlled 50-doc subset. No G3 condition beat the G2 best.

| Rank | Condition | Prag F1 | Pur F1 | Exact | Cost |
|------|-----------|---------|--------|-------|------|
| 1 | gpt_5_5 + Gan_cot_label (G2 carry) | **0.80** | 0.76 | 0.54 | $0.62 |
| 2 | gpt_5_5 + Gan_direct_label (G2 carry) | 0.76 | 0.76 | 0.60 | $0.62 |
| 3 | gpt_4_1_mini + Gan_direct_label (G2 baseline) | 0.66 | 0.62 | 0.48 | $0.02 |
| 4 | gpt_5_5 + Gan_fs_hard (G3 new) | 0.64 | 0.62 | 0.50 | $0.63 |

**G3 addendum — qwen35_b baseline (150 docs):**
`qwen_35b_local` + `Gan_g3_qwen` on 150 documents:
- Pragmatic micro-F1: 0.6933 | Purist: 0.6667 | Parse: 98.7% | Quote: 96.7%

**Learning:** Hard-case few-shot examples actively hurt performance on a controlled subset — the same pattern as Variant A for gemma4 in the local workstream (Phase 3) and H6fs for gemma4. Adding examples for specific hard patterns can harm model behavior on the easy majority. The best prompt from G2 remained the best prompt after G3. This suggests that further prompt iteration has diminishing returns; what is needed is either a retrieval mechanism or higher max_output_tokens.

---

## 6. G4-Retrieval: Initial Run (Superseded)

**Artifact:** `runs/gan_frequency/stage_g4_retrieval/`

**Idea:** Test whether providing retrieved frequency-relevant spans as highlighted context before extraction improves Pragmatic F1 above the 0.85 threshold.

**What happened:** GPT-5.5 parse failures returned. Root cause: `reasoning_tokens: 512` / `output_tokens: 512` — identical to G2. GPT-5.5 consumed its full token budget on internal reasoning before producing output.

**Learning:** **Always use `--max-output-tokens 2048` for GPT-5.5 (reasoning model).** The 512 default is completely inadequate for reasoning models and silently produces empty outputs that look like low scores.

---

## 7. G4-Retrieval Fixed Run (Authoritative)

**Artifact:** `runs/gan_frequency/stage_g4_fixed/`
**Fix:** `--max-output-tokens 2048`. All GPT-5.5 conditions now at 100% parse success.

**New harnesses:**
- `Gan_retrieval_highlight`: Retrieved frequency spans provided as highlighted context before extraction
- `Gan_retrieval_only_ablation`: Retrieved spans only, no extraction instruction (ablation control)

**Results:**

| Rank | Model | Harness | Prag F1 | Pur F1 | Exact | Parse | Quote |
|------|-------|---------|---------|-------|-------|-------|-------|
| 1 | gpt_5_5 | Gan_retrieval_highlight | **0.840** | 0.820 | **0.820** | 1.000 | 0.960 |
| 2 | gpt_5_5 | Gan_cot_label | 0.760 | 0.720 | 0.720 | 1.000 | 1.000 |
| 3 | gpt_5_5 | Gan_direct_label | 0.740 | 0.720 | 0.720 | 1.000 | 1.000 |
| 4 | qwen_35b_local | Gan_retrieval_highlight | 0.720 | 0.680 | 0.680 | 0.980 | 1.000 |
| 5 | qwen_35b_local | Gan_direct_label | 0.700 | 0.680 | 0.680 | 1.000 | 1.000 |
| 6 | qwen_35b_local | Gan_cot_label | 0.600 | 0.560 | 0.560 | 1.000 | 1.000 |
| 7 | gpt_5_5 | Gan_retrieval_only_ablation | 0.520 | 0.460 | 0.460 | 1.000 | 0.980 |
| 8 | qwen_35b_local | Gan_retrieval_only_ablation | 0.480 | 0.460 | 0.460 | 1.000 | 1.000 |

### 7.1 Key findings

**Retrieval highlight is the clear winner:** +8pp over cot_label (0.840 vs 0.760), 15 vs 23 errors.

**Ablation finding (critical):** retrieval-only (0.520) is 32pp below retrieval-highlight (0.840). Retrieved spans are useful salience cues, not sufficient context for accurate normalization. The extraction instruction is doing most of the work; retrieval primes the model's attention.

**Strict WP7 threshold (0.85) not met:** 0.840 is 1pp short on 50 documents, which is within sampling noise.

**GPT-5.5 + Gan_cot_label fixed run = 0.760:** Lower than G2's 0.800 because G2 parse failures artificially inflated precision (only parseable successful outputs were scored).

### 7.2 Error audit (fixed run)

- **gpt_5_5 + Gan_retrieval_highlight:** 15/50 errors — `other` (12), `gold_UNK_pred_numeric` (2), `cluster_collapsed` (1), `range_collapsed` (1). All genuine category mismatches; no parse artifacts.
- **gpt_5_5 + Gan_cot_label:** 23/50 errors — `other` (18) dominant.

The retrieval-highlight errors are qualitatively better: they are category boundary disagreements (e.g., `infrequent` vs `frequent` at the margin) rather than fundamental misreadings of the text.

### 7.3 Letter-level case study: Cluster pattern

**Letter excerpt (Gan synthetic):**
> "He reports having 3 seizures over 2 days last month, but otherwise has been seizure free. Prior to that cluster, his last seizure was 4 months ago."

**Gold (Pragmatic):** `infrequent`  
**Gold (Purist):** `1 per 3 month`

**GPT-5.5 + Direct label — ERROR:**
> Prediction: `frequent`  
> Reason: Attends to "3 seizures" without normalizing for cluster context.

**GPT-5.5 + Retrieval highlight — CORRECT:**
> Prediction: `infrequent`  
> Retrieved spans highlight: "seizure free" and "last seizure was 4 months ago"  
> Reason: Primed to attend to the disambiguating context.

### 7.4 Letter-level case study: Seizure-free interval

**Letter excerpt:**
> "Patient has been seizure free for 12 months. Previously had monthly seizures."

**Gold:** `seizure free for 12 month`

**GPT-5.5 + Direct label — ERROR:**
> Prediction: `frequent` (attends to "monthly seizures" — historical)

**GPT-5.5 + Retrieval highlight — CORRECT:**
> Prediction: `seizure free for 12 month` (retrieved span: "seizure free for 12 months")

---

## 8. Data Processing Stages

```
Raw Gan letter (.json)
    ↓
Gold audit & metric lock (G0)
    ↓
Retrieval: extract frequency-relevant spans (optional, G4)
    ↓
Prompt construction: direct / CoT / evidence / two-pass / retrieval-highlight
    ↓
API call (frontier) or Ollama native call (local)
    ↓
Response (normalized label string)
    ↓
Label converter: raw → Purist (10-bin) + Pragmatic (4-class)
    ↓
Scoring: micro-F1, exact accuracy, parse rate, quote validity
    ↓
Error audit: categorize mismatches
```

---

## 9. What We Left Behind

1. **Gan_two_pass:** Worst performer in G2 ($1.11, 0.340 Prag F1). The two-pass output parsing is brittle.
2. **Gan_fs_hard:** Reduced performance from 0.80 to 0.64. Hard-case few-shot examples harm when the model already has the right prior.
3. **Gan_evidence_label:** Attaching quotes impaired normalization. Not carried forward.
4. **512-token output budget:** Silently catastrophic for GPT-5.5. Fixed to 2048.

---

## 10. Outcomes & Pending Work

**Promoted condition:** `gpt_5_5` + `Gan_retrieval_highlight` + `--max-output-tokens 2048`  
**Baseline comparison:** `gpt_5_5` + `Gan_cot_label` + `--max-output-tokens 2048`  
**Full 1,500 local synthetic docs (G4-Full):** Not yet run. This is the main frequency result.

**Local model frequency:** qwen_35b_local achieved 0.700 Pragmatic F1 with direct label and 0.720 with retrieval highlight — competitive but below frontier. The gap is larger for frequency than for medication/seizure-type, suggesting frequency normalization requires stronger reasoning capabilities.

---

## 11. Discontinuity Addressed

**Discontinuity 5: Gan frequency ran in parallel without cross-pollination.**

The Gan workstream was a "fresh start" on a different benchmark rather than an evolution of the ExECTv2 pipeline. This was deliberate and justified:
- ExECTv2 frequency annotation was too sparse for meaningful claims (29.2% oracle ceiling).
- Gan was designed for frequency normalization with structured evidence.
- However, the lack of cross-pollination is a missed opportunity: Gan's retrieval-highlight approach was never tested on ExECTv2, and ExECTv2's evidence-grounding discipline was only partially ported to Gan.

**Recommendation for future work:** Test retrieval-highlight on ExECTv2 medication and seizure-type extraction. If retrieval helps frequency, it may help other fields too.

---

*Document compiled from: `docs/_master_timeline_and_narrative.md`, `docs/34_full_experiment_record.md` (§6), `docs/21_seizure_frequency_workstream.md`, `docs/26_g2_g3_frequency_results.md`, `docs/32_g3_deep_investigation.md`, and run artifacts in `runs/gan_frequency/stage_g4_fixed/`.*
