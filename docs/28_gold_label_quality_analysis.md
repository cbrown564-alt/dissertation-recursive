# Gold Label Quality Analysis

**Date:** 2026-05-10  
**Scope:** Exhaustive assessment of gold-standard label quality in both benchmark datasets and the consequent implications for all reported evaluation scores.

---

## Executive Summary

Both gold-standard datasets contain meaningful errors. The ExECT 2 (2025) NER dataset has pervasive span-boundary defects and a smaller number of high-severity semantic errors. The Gan (2026) seizure-frequency dataset has a roughly 16–40% rate of materially wrong or clinically ambiguous labels, depending on how conservatively you count. Neither dataset is "broken" — the ExECT labels correctly identify clinical concepts in most cases, and Gan's category-level scoring absorbs many gold errors — but both datasets have enough problems that the reported evaluation numbers should be interpreted with explicit caveats. The observation that model predictions sometimes appear more clinically accurate than the gold label is consistent with the audit findings and is not an artefact.

**Key conclusions:**

1. ExECT gold has pervasive span-boundary noise and selective deep errors (dose conflicts, truncated spans, under-specified normalizations). This degrades NER and medication-extraction F1 in ways that are not model-attributable.
2. Gan gold has a substantial rate of labelling errors that are absorbed by coarse category scoring (pragmatic: NS/infrequent/frequent/UNK). The 0.70–0.84 pragmatic F1 scores therefore slightly understate real model performance in some cases, while also masking genuine model errors that happen to land in the same category bin as a flawed gold label.
3. The more clinically precise a model's answer, the more likely it is to disagree with a flawed gold label — meaning precision improvements can show up as accuracy regressions under these evaluation setups.
4. Neither dataset is appropriate as a sole evaluation standard for a dissertation claiming to measure clinical NLP capability. Both should be cited with documented limitations and supplemented with qualitative evidence wherever the quantitative scores seem paradoxically low.

---

## 1. ExECT 2 (2025) Dataset

### 1.1 Dataset characteristics

ExECT 2 is the gold-standard NER corpus for the multi-field extraction evaluation (ExECT metrics: medication name F1, seizure-type F1, EEG/MRI accuracy, epilepsy-diagnosis accuracy, seizure-frequency per-letter accuracy). The corpus covers 200 synthetic epilepsy clinic letters annotated by double clinician review using Markup and a UMLS-based epilepsy concept list, reduced to a gold set after adjudication. Published human inter-annotator agreement was F1 = 0.73, reflecting genuine task difficulty.

The audit covered 20 of the 200 letters (EA0181–EA0200), yielding 218 annotations across 9 entity types.

### 1.2 Flaw catalogue

#### 1.2.1 Span-boundary errors (pervasive — affects ~23% of annotations)

| Type | Count |
|------|------:|
| Trailing hyphens/separators | 37 |
| Truncated final token | 9 |
| Leading separator | 2 |
| Mid-token start | 3 |

These are almost certainly artefacts of the Markup annotation tool's export format converting whitespace to hyphens. Examples:

- `EA0181`: `"ocal-dyscognitive-seizures"` — SeizureFrequency span starts one character too late; the matching Diagnosis span is correctly `"focal-dyscognitive-seizures"`.
- `EA0184`: `"typical-absenc"` and `"typical-absen"` — both truncated rather than selecting `"typical absences"`.
- `EA0188`: `"eiz"` for PatientHistory and `"ondary-generalised-seiz"` for Diagnosis — both start and end mid-token.
- `EA0186`: `"epileps"`, `"seizur"`, `"focal-to-bilateral-convulsive-seizur"` — all truncated.
- `EA0200`: `"loss-of-consciousnes"` — final character dropped.

**Evaluation impact:** Span-boundary errors corrupt the evidence-overlap scoring in `evaluate.py:evidence_overlaps_gold()`. A model that extracts the correct full token will fail to match a gold span that is one character too short. This systematically penalises models for being more precise. The impact is primarily on evidence scores (`evidence_scores`, `semantic_support`) rather than field-level correctness, but it also affects any span-level NER metric.

#### 1.2.2 Duplicate and conflicting labels (high-severity, affects ~8 cases in the 20-letter sample)

| Example | Problem |
|---------|---------|
| EA0183: two Prescription labels on `"Sodium-Valproate"` | Doses listed as 800 mg and 700 mg — a direct factual conflict |
| EA0195: two Tegretol labels | One span `"Tegretol-"` assigned 600 mg; `"Tegretol-400mg-in-the-morning"` assigned 400 mg |
| EA0194: two SeizureFrequency labels on the same span | One says `NumberOfSeizures: 0` (seizure-free since 23/5/2019); the other says `LowerNumberOfSeizures: 1, UpperNumberOfSeizures: 2 per year` |
| EA0198: two Onset labels on `"epilepsy"` | One says onset age 23 years; the other says 15 years |

**Evaluation impact:** The medication scoring compares predicted medication sets against gold medication sets. When the gold set contains two contradictory entries for the same drug (e.g. sodium valproate at 800 mg and at 700 mg), a model that correctly identifies the dose will match one gold entry and miss the other, generating a false negative. The medication_full F1 metric is directly corrupted by this pattern. The seizure-frequency per-letter metric is less affected (it matches against any gold candidate), but the conflicting temporal-scope case in EA0194 represents a genuine labelling failure that cannot be resolved without the full letter.

#### 1.2.3 Under-specified CUIPhrase normalization (moderate, affects ~15% of labels)

| Raw text | Assigned CUIPhrase | Problem |
|----------|--------------------|---------|
| `"generalised-tonic-clonic-seizures"` | `"generalised"` | Loses seizure-type specificity |
| `"drug-refractory"` | `"drug"` | Reduces to non-clinical generic |
| `"focal-motor-seizures"` | `"focal"` | Loses semiological specificity |
| `"ischaemic-damage"` (EpilepsyCause) | `"brain"` | Too vague |
| `"transient-loss-of-consciousness"` | `"Transient"` | Not a meaningful UMLS concept |
| `"occipital-lobe)-epilepsy"` | `"Occipital"` | Anatomical-only, malformed span |

**Evaluation impact:** The `canonical_seizure_type()` and `canonical_diagnosis()` normalization functions in `normalization.py` compare predicted concepts against gold CUIs/CUIPhrases. A model that extracts `"focal motor seizures"` and normalizes it correctly to `focal-motor` will not match a gold label that normalized the same phrase to `"focal"`. This creates false negatives in seizure-type F1 and epilepsy-diagnosis F1, and penalises models that are more specific than the gold.

#### 1.2.4 Medication annotation errors (moderate, ~17 labels affected)

- 17 Prescription labels have `DrugDose` populated but the annotated span contains no number (e.g., EA0181 labels only `"lamotrigine"` with dose 150 mg twice daily). The dose is derived from surrounding context invisible in the JSON.
- DrugName errors: EA0193 maps `"Topiramate"` to `DrugName: "top"` (non-canonical abbreviation). EA0188 stores `"Brivitiracetam"` as a misspelled DrugName while normalizing the CUI to `"brivaracetam"`.
- Dose units are sometimes absent where present in the text.

**Evaluation impact:** `normalize_dose()` and `canonical_medication_name()` are applied to both gold and predicted entries. The misspelled DrugNames and incomplete dose spans degrade the medication F1 baseline and make it harder to interpret whether F1 changes are due to model improvement or gold noise.

#### 1.2.5 Seizure-frequency labelling errors (moderate-to-high, ~6 of 32 annotations)

- EA0194 assigns contradictory temporal interpretations to the same span (see 1.2.2 above).
- EA0188: SeizureFrequency span `"secondary-generalised-seizure"` says 1 per month, but the Diagnosis span covering the same event is `"ondary-generalised-seiz"` (truncated).
- EA0193: SeizureFrequency label for `"Bilateral-convulsive-seizures"` has `NumberOfSeizures: 0` since a date but no CUI or CUIPhrase, while the matching Diagnosis span has CUI/CUIPhrase — inconsistent schema application.
- EA0181: SeizureFrequency `"seizures-"` labelled as 10–15 over 2 days; a related span `"ocal-dyscognitive-seizures"` only says `FrequencyChange: Frequent` with no count/period — incomplete label.

**Evaluation impact:** The per-letter seizure-frequency metric (`current_seizure_frequency_per_letter_accuracy`) matches the extracted value against any gold candidate parsed from the CSV columns or raw span. When gold spans are truncated or gold attributes are inconsistent, the parser may fail to parse the gold correctly, reducing the oracle ceiling without any model fault.

#### 1.2.6 Severity summary by field

| Field | Gold quality | Expected F1 inflation/deflation |
|-------|-------------|----------------------------------|
| Medication name | Moderate (misspelling, non-canonical abbreviations) | Slight deflation (FN from mismatches) |
| Medication dose | Poor (conflicts, span-only labelling) | Moderate deflation |
| Medication dose_unit | Moderate (occasional absence) | Minor deflation |
| Seizure type | Moderate (under-specified CUIPhrases) | Moderate deflation |
| Epilepsy diagnosis | Moderate (under-specified, broad CUIPhrases) | Minor-to-moderate deflation |
| EEG / MRI | Good (mostly consistent) | Minimal impact |
| Seizure frequency per-letter | Mixed (truncated spans, contradictions) | Moderate deflation |
| Evidence overlap | Poor (span boundary artefacts) | Moderate deflation |

---

## 2. Gan (2026) Dataset

### 2.1 Dataset characteristics

The Gan dataset provides seizure-frequency labels in a normalized string format (`"N per period"`, `"seizure free for N month"`, `"unknown"`, `"no seizure frequency reference"`, cluster variants). Our evaluation scores these via two category mappings:

- **Pragmatic:** 4 classes — NS (no seizures), infrequent (>0 to ≤1.1/month), frequent (>1.1 to 999/month), UNK.
- **Purist:** ~10 finer classes based on rate breakpoints.

The sample audit covered 50 letters from `synthetic_data_subset_1500.json`. All 1,500 are the "synthetic" subset of the Gan corpus; the paper's headline 0.847 pragmatic F1 was reported on their Real(300) set.

### 2.2 Flaw catalogue

#### 2.2.1 Cluster normalization errors (high-severity, ~4 confirmed wrong labels + multiple borderline)

The most consequential systematic error is treating cluster days as single seizures:

| Sample | Gold label | Correct interpretation |
|--------|-----------|----------------------|
| 10 / row 16394 | `1 per 2 to 4 day` | Letter says seizures occur *in clusters* every 2–4 days; cluster structure is lost |
| 15 / row 16618 | `1 per 5 day` | "Clusters spaced 5 days apart" plus "brief periods of daily seizures"; cluster structure lost |
| 24 / row 13069 | `2 per 5 month` | One GTC after five seizure-free months preceded by a *cluster of absences*; counting the cluster as 1 event undercounts |
| 28 / row 15262 | `multiple cluster per 13 month, multiple per cluster` | Serious temporal error: the 13-month interval refers to the last convulsive seizure, not cluster frequency |

**Note on cluster normalisation (agreed scope):** The key clinical question for frequency evaluation is whether a cluster day is correctly identified as a seizure day — not whether the exact within-cluster count is preserved. A label of `"1 per 3 day"` (one cluster period every 3 days) is clinically acceptable even if the gold uses `"1 cluster per 3 day, N per cluster"`. The pragmatic category mapping already handles this: both forms typically fall in the same bin. Cluster-vs-plain-rate is therefore noted as a secondary labelling quirk rather than a primary evaluation error. The full audit (`docs/29_gold_audit_plan.md`) will programmatically flag cluster cases and verify whether collapse changes the pragmatic category, so the extent of any category-level impact will be quantified.

**Evaluation impact at pragmatic category level (where cluster collapse does change category):** `2 per 5 month` = 0.4/month → infrequent; if the correct interpretation is a cluster where total events push past 1.1/month → frequent. These cross-category cases are a genuine evaluation concern and will be specifically flagged in the G6 audit check. In the 50-sample, approximately 1–2 cases appeared to be in this class.

#### 2.2.2 Over-inferred time windows (moderate, ~4 confirmed + multiple borderline)

| Sample | Gold label | Issue |
|--------|-----------|-------|
| 30 / row 15317 | `2 to 3 per 15 month` | "2–3 single jerks remain" is not clearly bounded to 15 months |
| 33 / row 4378 | `3 per 2 month` | Ambiguous diary dates (could be UK format 7 March, 7 August, 9 May, not 7/3, 7/8, 9/5 as inferred) |
| 28 / row 15262 | `multiple cluster per 13 month` | Temporal confusion as above |
| 9 / row 8568 | `seizure free for multiple month` | "No events since last assessment" — no date given |

**Evaluation impact:** When the gold label is an over-inferred rate, a model that honestly returns `"unknown"` or a different period is penalised by both exact accuracy and pragmatic category accuracy. The model's response may be epistemically more appropriate. Over-inferred rates that result in a wrong pragmatic category are the highest-risk sub-class.

#### 2.2.3 Imprecise seizure-free labels (moderate, ~6 borderline cases)

| Sample | Gold label | Issue |
|--------|-----------|-------|
| 40 / row 8790 | `seizure free for multiple month` | Letter explicitly says "no events over the past six months" — should be `seizure free for 6 month` |
| 43 / row 8006 | `seizure free for multiple month` | Letter says no blackouts or focal impaired-awareness episodes over past six months |
| 35 / row 8858 | `seizure free for multiple month` | Levetiracetam started July 2024, clinic date Oct 2025 → ~15 months; label is vague when duration is computable |

**Evaluation impact:** At pragmatic level, all `seizure free for N month` variants map to NS, so these do not cause category errors. They cause exact label accuracy losses when a model correctly resolves the duration (e.g., outputs `seizure free for 6 month` against a gold label of `seizure free for multiple month`). This creates a paradox: a more careful, letter-reading model scores lower on exact accuracy. These cases likely account for some of the gap between exact accuracy (~52–58%) and pragmatic F1 (~70–76%) in our results.

#### 2.2.4 Evidence metadata mismatches (confirmed at full scale: 197/1,500 = 13.1%)

| Source row | Final label | `reference[0]` value |
|-----------|------------|---------------------|
| 8264 | `seizure free for 4 month` | `unknown` |
| 5906 | `1 cluster per 3 week, multiple per cluster` | `unknown` |
| 10630 | `multiple cluster per 2 week, 5 per cluster` | `unknown` |
| 7316 | `1 to 2 per month` | `unknown` |

The `reference` field in the Gan dataset is used in our evaluation as a secondary source for evidence-grounded scoring. When `reference[0]` says `unknown` but the final label is a specific frequency, the evidence-grounding logic (`load_gan_examples()`, which reads `evidence_reference` from `reference[1]`) may extract wrong or absent evidence, degrading the evidence-quality metrics.

**Full-dataset count confirmed:** A query on all 1,500 records found **197 records (13.1%)** where the final label does not match `reference[0]` — higher than the 8% sample estimate. This is a confirmed finding, not an extrapolation. As above, these do not cause category-level scoring errors (the final label drives scoring), but they corrupt evidence-quality analysis and raise questions about the reliability of the annotation workflow at a meaningful scale.

#### 2.2.5 Contradictory letter contents (moderate, ~4 confirmed cases)

Some synthetic letters contain mutually inconsistent frequency statements. Examples:

- Row 12584 (sample 46): "weekly absences persist" followed by "no reported episodes since last visit."
- Row 12645 (sample 49): "daily absences" clearly described, but later "since the last clinic visit, no further seizures have been reported."

These are synthetic data generation artefacts. The gold label is based on the annotator's clinical interpretation of which statement to prioritise. A model that reads the letter carefully and chooses the same prioritisation will match gold; one that prioritises the other statement will miss, but neither answer is definitively wrong.

**Evaluation impact:** These cases create irreducible noise in the scoring. The pragmatic category of the gold label may or may not match the pragmatic category of a reasonable alternative interpretation. With ~8% of the sample affected, this is a non-trivial source of variance.

#### 2.2.6 Encoding corruption artefacts

The synthetic letters contain encoding errors: `Ã‚Â·`, `ï¿½`, `â€` sequences appear as garbled text. These are UTF-8 double-encoding artefacts from the synthetic data generation pipeline. They do not corrupt the frequency labels directly, but they degrade letter readability and may cause retrieval patterns (`retrieve_frequency_spans()`) to miss or misidentify frequency-relevant sentences.

#### 2.2.7 Severity summary

| Error type | Confirmed cases / 50 | Estimated rate | Pragmatic category impact |
|-----------|---------------------|----------------|--------------------------|
| Cluster collapsed to plain rate | 4 | ~8% | Sometimes causes category error |
| Over-inferred time window | 4 | ~8% | Sometimes causes category error |
| Imprecise seizure-free duration | 6 | ~12% | Exact accuracy only (NS either way) |
| Reference metadata mismatch | 4 | ~8% | Evidence quality only |
| Contradictory letter | 4 | ~8% | Irreducible noise |
| Borderline (non-epileptic events, no-date-seizure-free) | 9 | ~18% | Category-level ambiguity |

**Overall estimate:** ~16% of cases have a likely-wrong gold label (cluster + time-window errors that change or could change the pragmatic category); ~12% are exact-accuracy losses with correct category; ~18% are genuine ambiguity. The 60% "robust" cases in the audit are well-supported direct rates or clear unknowns.

---

## 3. Impact on Reported Evaluation Numbers

### 3.1 Gan pragmatic F1 scores

| Condition | Reported Prag F1 | Expected direction of gold error bias |
|-----------|-----------------|--------------------------------------|
| qwen_35b + Gan_direct_label (G2, n=150) | 0.700 | Mixed: cluster errors penalise good models; imprecise-seizure-free errors penalise exact-but-correct models |
| gpt_5_5 + Gan_retrieval_highlight (G4-Fixed, n=50) | 0.840 | Same |
| Gan published Real(300) benchmark | 0.847 | Same errors present in Gan gold overall |

At pragmatic F1 = 0.70 with ~16% likely-wrong gold, the true model capability implied is probably 0.72–0.78 (if we could re-score against a corrected gold). This is a meaningful adjustment but does not change the dissertation claim structure — we are still below the Gan published synthetic benchmark, and the error direction is roughly symmetric: some cases where the model is penalised for being right, and some cases where a wrong model answer accidentally matches a wrong gold label and is credited.

The cluster-collapse errors are the most directionally concerning: a model that correctly identifies cluster structure will be penalised against a gold label that collapsed to a plain rate. Our harnesses do not heavily train on cluster detection, so this probably accounts for a small number of cases, but it means the "cluster_collapsed_to_plain_rate" error bucket from our error audit may include both genuine model errors and model-is-right-gold-is-wrong cases.

### 3.2 ExECT multi-field F1 scores

The ExECT evaluation currently reports, for the best systems:

- `medication_name_f1`: ~0.80–0.90 (generally stable because canonical drug names are robust)
- `medication_full_f1`: ~0.50–0.65 (degrades sharply due to dose/frequency gold noise)
- `seizure_type_f1`: ~0.60–0.70 (affected by under-specified CUIPhrases)
- `current_seizure_frequency_per_letter_accuracy`: ~0.60–0.70 (affected by truncated gold spans)
- `epilepsy_diagnosis_accuracy`: ~0.70–0.85 (affected by under-specified CUIPhrases)
- `eeg/mri_accuracy`: ~0.80–0.90 (least affected by gold noise)

**Estimated gold-noise component of observed errors:**

| Metric | Estimated gold-noise share of observed FN |
|--------|------------------------------------------|
| medication_full F1 | 15–25% (dose conflicts, span-only labelling) |
| seizure_type F1 | 10–20% (under-specified CUIPhrases) |
| epilepsy_diagnosis accuracy | 5–15% (under-specified CUIPhrases) |
| frequency per-letter accuracy | 10–15% (truncated gold spans, contradictions) |
| evidence overlap | 20–30% (span-boundary artefacts) |

These are estimates, not measured values. The implication is that true model performance on medication-full F1 and seizure-type F1 is plausibly 5–15 points higher than reported, if evaluated against clean gold.

### 3.3 The "predicted answer is more accurate" observation

This is expected from the above analysis, and its occurrence is evidence that gold noise is real and directional in some cases. Specific expected manifestations:

1. **Medication dose:** A model extracts `sodium valproate 750 mg twice daily` from a letter; gold has two conflicting entries (800 mg and 700 mg) from EA0183-style conflicts. Neither matches. The model is wrong on both, but it may be clinically closer to the truth than either gold entry.
2. **Seizure-free duration:** A model reads "no seizures for the past six months" and outputs `seizure free for 6 month`; gold says `seizure free for multiple month`. Model is correct; gold is imprecise. Exact accuracy: 0. Pragmatic accuracy: 1 (both NS). This is the cleanest case where our metric structure already partially handles it.
3. **Cluster detection:** A model outputs `2 cluster per month, 5 per cluster` for a cluster-pattern letter; gold says `2 per month` (collapsed). Model is more clinically accurate; model fails the exact and likely the per-letter accuracy check.
4. **CUIPhrase specificity:** A model predicts `focal motor seizures`; gold CUIPhrase is `focal`. A specificity-aware matching function would credit the model; exact string matching does not.

These cases are not random noise — they systematically bias scores against more capable models that extract richer and more specific information.

---

## 4. Calibrated Interpretation for Dissertation Use

### 4.1 What the scores mean

The reported evaluation numbers are valid measurements of agreement with the provided gold labels. They are not clean measurements of clinical extraction quality. The distinction matters when:

- Comparing against the Gan published benchmark (the same gold-label quality issues exist in the Gan paper's evaluation, so the comparison is internally valid but does not fully reflect absolute clinical accuracy).
- Making claims about medication extraction quality (the dose conflicts and span artefacts in ExECT significantly depress medication_full F1 below model capability).
- Interpreting seizure-type and diagnosis F1 (CUIPhrase under-specification creates a downward ceiling effect).

### 4.2 What remains valid

- **Relative rankings between systems** are mostly valid: gold noise is constant across systems, so system A consistently outperforming system B reflects genuine capability differences.
- **EEG/MRI accuracy** is relatively unaffected by gold noise and is the most cleanly interpreted metric.
- **Medication name F1** (not including dose/unit/frequency) is robust because canonical drug name matching is tolerant of spelling variation.
- **Pragmatic F1 on Gan** is more robust than exact label accuracy because the category mapping absorbs many gold imprecisions; the seizure-free cases where the model is penalised for being more specific than gold are largely absorbed into the NS category.
- **Error bucket analysis** is still informative: the counts of cluster_collapsed errors, threshold flips, and so on reflect real model failure modes, though some bucket members may be gold errors.

### 4.3 How to frame this in the dissertation

**Recommended framing (applies to all evaluation chapters):**

> "Evaluation scores are reported against the provided gold labels, which were annotated by clinicians but are not error-free. An audit of [20 ExECT / 50 Gan] records identified [span-boundary defects affecting ~23% of ExECT annotations] and [~16% material labelling errors and ~18% genuine ambiguity in the Gan sample]. These errors systematically depress F1 relative to true model capability on fields requiring precise normalization (medication dose, seizure-type specificity, exact seizure-free duration), while having less impact on coarser metrics (pragmatic category F1, drug name F1, EEG/MRI accuracy). Reported scores should therefore be interpreted as lower bounds on clinical extraction quality for the precision-sensitive fields."

**Specific claims that need qualification:**

- Do not claim medication_full F1 reflects actual medication extraction quality without noting the dose-conflict artefacts.
- Do not compare exact Gan label accuracy directly with the paper's Gan benchmark — the pragmatic F1 comparison is the appropriate comparison level.
- Seizure-type F1 improvements across systems are real, but the absolute level is depressed by CUIPhrase specificity mismatch.

### 4.4 Qualitative supplementation

The "predicted answer is more accurate than gold" observation is a valuable qualitative finding in its own right. It can be framed as:

> "Qualitative review revealed cases in which the extracted output was more clinically precise than the gold label — for example, correctly identifying a seizure-free duration as 'six months' where the gold label used the vague form 'multiple months', or correctly preserving cluster structure that the gold label had collapsed to a plain rate. This pattern is consistent with the audit findings and suggests that quantitative scores understate model capability on precision-sensitive extraction tasks."

---

## 5. Recommendations

### For the dissertation

1. **Include the gold-label quality audit as a documented limitation** in the Methods or Evaluation chapter. The numbers are in this document and the two inspection files.
2. **Report pragmatic F1 as the primary Gan metric** (not exact accuracy). This is already our practice and is correct — it absorbs most of the gold imprecision.
3. **Report medication_name F1 as the primary medication metric**, with medication_full F1 as secondary and with the caveat about dose conflicts.
4. **Cite the published inter-annotator agreement (F1 = 0.73) for ExECT** as an external validity anchor. Our models at 0.70–0.85 on the cleanest fields are operating near the human ceiling, not far below it.
5. **Note specific cases where predicted outputs appeared more accurate**, as a qualitative finding rather than a scored result.

### For the evaluation code

No code changes are required to accommodate these findings — the metrics are correctly implemented against the available gold. If a corrected gold were produced, the existing evaluation pipeline would immediately produce better numbers. Specifically:

- Fixing span-boundary artefacts (strip trailing/leading hyphens) would improve evidence-overlap scores by an estimated 5–10 points.
- Resolving dose conflicts (one gold entry per drug per document) would improve medication_full F1 by an estimated 3–8 points.
- Replacing `"focal"`, `"generalised"` etc. with full CUIPhrases would improve seizure-type F1 by an estimated 5–15 points.

None of these corrections need to happen for the dissertation to be defensible, but they should be noted as future directions.

---

## Appendix: Flaw Rate Summary

| Dataset | Total sample | Material errors | Ambiguous/borderline | Robust |
|---------|-------------|-----------------|----------------------|--------|
| Gan (2026), n=50 | 50 letters | ~8 (16%) | ~12 (24%) | ~30 (60%) |
| ExECT 2 (2025), n=20 | 218 annotations | ~15 (7% severe) | ~50 (23% boundary) | ~153 (70%) |

ExECT severe errors (doses, truncated words, temporal contradictions) affect ~7% of individual annotations; boundary artefacts (trailing hyphens etc.) affect ~23% but are lower-severity. Combined, ~30% of ExECT annotations have at least one quality issue of some kind.

---

*Produced from: `data-examination/EXeCT_20_inspection.txt`, `data-examination/gan_50_inspection.txt`, `src/evaluate.py`, `src/gan_frequency.py`, and `docs/26_g2_g3_frequency_results.md`.*
