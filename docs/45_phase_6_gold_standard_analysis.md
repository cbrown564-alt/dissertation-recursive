# Phase 6 — Gold Standard Quality & the Annotation Ceiling

**Date:** 2026-05-10–12  
**Scope:** Deep qualitative and quantitative review of ExECTv2 and Gan gold labels.  
**Purpose:** Determine how much of the observed "model error" is actually annotation gap, benchmark mismatch, or gold-standard ambiguity.  
**Status:** Complete. Forms the metrological foundation for all claims.

---

## 1. Aims & Research Questions

Every phase document reports F1 scores, accuracy, and error audits. But these numbers are only meaningful if the ground truth is itself trustworthy. This document asks:

1. What proportion of observed errors are actually annotation gaps rather than model failures?
2. What is the hard performance ceiling for each field, given perfect extraction but real annotation quality?
3. When a model extracts clinically accurate information that does not match the gold label, is the model wrong or is the benchmark mismatched?
4. How does ExECTv2 gold quality compare to Gan gold quality, and what does this imply for cross-benchmark claims?

**What we knew when we started:**
- Phase 2 (Recovery) had produced the aggregation oracle, showing 29.2% of seizure frequency was unscoreable even with perfect extraction.
- Phase 3 (Local Models) had found that `unknown seizure type` misses were consistent (13–15/26) across all models and scales.
- These findings triggered a systematic gold audit rather than more prompt engineering.

---

## 2. The Oracle as Trigger

The aggregation oracle (Phase 2, §4.6) estimated the hard performance ceiling by asking: "What score would be achieved with perfect extraction but real ExECTv2 annotation gaps?"

| Field | Oracle Failure Rate | Interpretation |
|-------|---------------------|----------------|
| Medication name | **0.0%** | Ceiling is 100% F1; all failures are extractable |
| Medication full tuple | 10.8% | 11% of docs have annotation ambiguity at tuple level |
| Seizure type | 13.3% | 13% irreducible from annotation gaps |
| Epilepsy diagnosis | 17.5% | 18% irreducible |
| Seizure frequency | **29.2%** | 29% hard ceiling — even perfect extraction cannot score |
| Freq-type linkage | 29.2% | Same hard ceiling as frequency |

**Why this triggered gold audits:** A 29.2% hard ceiling is not a minor footnote — it is the dominant explanatory factor for why frequency scores remain low. Before accepting "models can't extract frequency," we needed to determine whether the gold itself was the problem.

---

## 3. ExECTv2 Annotation Gap Taxonomy

### 3.1 Temporal sparsity

ExECTv2 provides timing columns (`YearDate`, `NumberOfTimePeriods`, `TimePeriod`) but these are sparse. In ~15% of documents, a medication or seizure mention lacks explicit temporal anchoring, forcing the scorer to assume "current" by default. When the model makes a different temporal assumption (e.g., inferring "previous" from context), it is scored as wrong even when clinically reasonable.

**Example (EA0006):** A letter states "He was on carbamazepine previously" but the gold labels it as current because the temporal column is empty. The model correctly extracts it as previous and is penalized.

### 3.2 Meta-label ambiguity: `unknown seizure type`

The `unknown seizure type` label is used when the annotator cannot determine seizure type from the letter. It is a meta-judgment about **absence of information**. However, models consistently attempt to infer a specific type from clinical context:

- Patient reports "some episodes but unsure what they are" → Gold: `unknown seizure type` → Model: `focal seizure`
- The model is not hallucinating; it is making a reasonable clinical inference from the context of an epilepsy clinic letter.

**Count:** 13–15 misses out of 26 documents with this gold label, consistent across 4B–35B models.

**Verdict:** This is a structural difference between what models do (infer from context) and what the annotation scheme requires (abstain when uncertain). It is not a model capability gap.

### 3.3 Frequency multi-mention mismatch

ExECTv2 expects **all frequency mentions** per letter to be extracted. Gan expects **a single normalized frequency**. This creates a fundamental mismatch:

- Letter: "3 seizures over 2 days last month, otherwise seizure free" → ExECTv2 gold: multiple frequency entities (cluster + seizure-free) → Gan gold: `infrequent` (normalized)
- A model that extracts "3 per 2 days" is correct by ExECTv2 standards but wrong by Gan standards.
- A model that extracts "infrequent" is correct by Gan standards but may miss the ExECTv2 multi-mention requirement.

**Verdict:** The two benchmarks measure different tasks. Frequency claims should be made on Gan, where the task is well-defined, not on ExECTv2 where the annotation scheme is inconsistent with clinical utility.

### 3.4 Medication tuple ambiguity

10.8% of documents have annotation ambiguity at the medication tuple level:
- **Split-dose ambiguity:** "500mg morning, 250mg evening" → Is this one medication with split dose, or two medications? ExECTv2 annotates as one entity; some models extract as two.
- **"As required" (PRN) frequency:** "clobazam 10mg nocte as required" → Frequency is irregular; gold may omit frequency while model extracts "nocte as required."
- **Brand vs generic:** Gold uses generic name; model extracts brand name (e.g., "Keppra" vs "levetiracetam"). After ASM synonym expansion (Phase 2), this is resolved in scoring but not in the original gold.

### 3.5 Diagnosis granularity

ExECTv2 uses BRAT standoff with CUIPhrase mappings (e.g., `symptomatic-structural-focal-epilepsy`). The benchmark scorer collapses these to 4 categories (`focal`, `generalised`, `combined`, `unknown`).

A model extracting "right temporal lobe epilepsy" is clinically precise but does not match the gold `symptomatic-structural-focal-epilepsy` string. The collapsed-label scorer (Phase 2) fixes this, but strict scoring penalizes clinically accurate granularity differences.

---

## 4. Letter-Level Qualitative Reviews

### 4.1 EA0001: Medication tuple ambiguity

**Letter excerpt:**
> "He takes sodium valproate 500mg in the morning and 500mg in the evening, and levetiracetam 250mg bd."

**Gold entities:**
```json
[
  {"entity":"Prescription","text":"sodium-valproate-500-mg-in-the-morning-and-500-mg-in-the-evening","attributes":{"DrugName":"sodium valproate","DrugDose":"500","DoseUnit":"mg","Frequency":"2"}},
  {"entity":"Prescription","text":"levetiracetam-250-mg-bd","attributes":{"DrugName":"levetiracetam","DrugDose":"250","DoseUnit":"mg","Frequency":"2"}}
]
```

**Model extraction (qwen3.6:27b H6):**
```json
[
  {"name":"sodium valproate","dose":"500","unit":"mg","frequency":"twice daily"},
  {"name":"levetiracetam","dose":"250","unit":"mg","frequency":"bd"}
]
```

**Analysis:** The model correctly identifies both medications and their doses. The frequency "twice daily" vs "bd" is a normalization match (handled by Phase 2 scorer). However, the gold encodes the split-dose as a single frequency value of "2" (twice daily), while the letter text is more nuanced. The model is clinically correct; the gold is structurally simplified.

**Verdict:** Not a model error. A per-component scorer handles this correctly.

### 4.2 EA0012: Seizure-free hallucination vs gold ambiguity

**Letter excerpt:**
> "She has been seizure free for the last 18 months. Previously she experienced focal seizures with impaired awareness, but these have not recurred since her medication was optimised."

**Gold:** `seizure_types: ["seizure free"]`

**Model (qwen3.5:9b H6):** `seizure_types: ["focal seizure with impaired awareness"]`

**Analysis:** The model extracts the historical type. This is scored as a false positive and a false negative (missed `seizure free`). But the letter explicitly mentions both "seizure free" AND "previously ... focal seizures." The model attended to the wrong sentence. This is a genuine model error — but one that is addressable via few-shot guidance (H6fs fixes it).

**Verdict:** Model error (attention misallocation), but fixable.

### 4.3 EA0034: Unknown seizure type vs model inference

**Letter excerpt:**
> "The patient reports occasional episodes. She is unsure whether these are seizures or something else. We have not captured these on EEG."

**Gold:** `seizure_types: ["unknown seizure type"]`

**Model (all systems):** `seizure_types: ["focal seizure"]` or `["generalised tonic-clonic seizure"]`

**Analysis:** The annotator could not determine seizure type from the ambiguous description and correctly used the meta-label. The model, however, infers a specific type from the context of an epilepsy clinic letter. Is this wrong? Clinically, a neurologist reading this letter might also suspect focal seizures given the EEG correlation attempt. The model is making a reasonable inference; the gold is correctly abstaining.

**Verdict:** Structural benchmark-model mismatch, not a capability failure.

### 4.4 EA0056: Frequency contradiction

**Letter excerpt:**
> "Currently having about 1 seizure per month. Last month she had a cluster of 4 seizures over 3 days."

**Gold:** Two `SeizureFrequency` entities: `1 per 1 month` AND `4 per 3 days`

**Model (S2):** `seizure_frequency: {value: "1", period: "month"}` (only the first mention)

**Analysis:** The model extracts the first frequency mention and misses the cluster. Under ExECTv2 scoring (multi-mention), this is a partial miss. Under Gan scoring (single normalized), the gold would be `infrequent` (normalized from the overall pattern). The model's extraction is clinically informative but incomplete.

**Verdict:** Task mismatch. ExECTv2 wants all mentions; Gan wants a single clinical judgment. The model behavior is more aligned with Gan's design.

---

## 5. Quantitative Gold Audit Results

From `docs/30_gold_audit_results.md` and `docs/38_gold_standard_quality_audit.md`:

| Metric | ExECTv2 | Gan 2026 |
|--------|---------|----------|
| Documents | 200 | 1,500 |
| Annotation format | BRAT standoff | JSON with rationale |
| Frequency design | Multi-mention | Single normalized |
| Evidence quotes | No | Yes (structured spans) |
| Rationale fields | No | Yes (annotator reasoning) |
| Temporal columns | Sparse | Dense |
| Label normalization | Post-hoc (project) | Built-in |
| Inter-annotator proxy | None | Implicit (synthetic generation) |

**Programmatic audits (ExECTv2):**
- 12.3% of medication entities have incomplete tuple fields (missing dose, unit, or frequency)
- 8.7% of seizure type entities have conflicting temporality markers
- 15.4% of documents have at least one orphaned entity (text span does not align with letter)
- 6.2% of `SeizureFrequency` entities have null or contradictory `TimePeriod` values

---

## 6. Clinical Accuracy vs Gold Standard Tension

From `docs/37_clinical_accuracy_vs_gold_standard_tension.md`:

There are systematic cases where the model extracts **clinically accurate** information that does not match the gold label:

| Scenario | Model Output | Gold Label | Assessment |
|----------|--------------|------------|------------|
| Granular diagnosis | "symptomatic structural focal epilepsy" | "focal epilepsy" | Model is more specific; collapsed scorer maps both to "focal" |
| Brand name | "Keppra" | "levetiracetam" | Clinically equivalent; ASM synonym expansion resolves |
| Frequency clinical judgment | "infrequent" | "1 per 3 month" | Model gives category; gold gives exact rate; both valid |
| Historical medication | "carbamazepine (previous)" | "carbamazepine" (current) | Model is temporally precise; gold lacks temporal marker |
| Seizure-free status | "seizure free" | `[]` (empty) | Gold omits when no type specified; model explicitly states |

**Proposed criteria for "valid" extraction even when gold mismatches:**
1. **Semantic equivalence:** Does the extraction convey the same clinical meaning under domain normalization?
2. **Temporal correctness:** Is the extraction consistent with the letter's temporal markers?
3. **Granularity match:** Is the extraction at the same level of specificity as the task requires?
4. **Evidence presence:** Is there verbatim text in the letter supporting the extraction?

If all four criteria are met, the extraction should be considered correct regardless of exact gold-string match.

---

## 7. Comparison: ExECTv2 vs Gan Gold Quality

| Dimension | ExECTv2 | Gan 2026 | Implication |
|-----------|---------|----------|-------------|
| **Primary task** | Entity extraction | Frequency normalization | Different architectures needed |
| **Frequency design** | Multi-mention (all spans) | Single normalized label | Gan is closer to clinical utility |
| **Annotation density** | Sparse temporal columns | Dense structured fields | Gan has fewer gaps |
| **Evidence grounding** | Not required in gold | Required (spans + rationale) | Gan supports evidence-based claims |
| **Label taxonomy** | 14 seizure types, open meds | 4 pragmatic + 10 purist | Gan is designed for classification |
| **Synthetic generation** | Rule-based + manual | LLM-generated + normalized | Gan has generation artifacts but better structure |

**Key insight:** ExECTv2 was designed for information extraction research (entity recognition, relation extraction). Gan was designed for frequency normalization research. Neither is "better" — they are optimized for different claims. The dissertation uses ExECTv2 for medication/seizure-type/diagnosis claims and Gan for frequency claims.

---

## 8. Implications for Claims

### 8.1 Bounding model failure by oracle rate

Any claim of "model failure" must be gated by the oracle failure rate:

- **Medication name:** 0% oracle failure → all failures are extractable. Claim: models can achieve ≥0.90 with better prompts or larger models.
- **Medication full tuple:** 10.8% oracle failure → claims above ~0.89 are impossible. Current best: 0.769 (test). Room for improvement remains.
- **Seizure type (strict):** 13.3% oracle failure + meta-label mismatch → claims above ~0.87 are impossible. Use collapsed labels.
- **Seizure frequency (ExECTv2):** 29.2% oracle failure → maximum achievable ~0.71. Current: 0.175. **Do not claim frequency on ExECTv2.**
- **Seizure frequency (Gan):** No oracle calculated yet, but structured gold suggests ceiling is higher. G4-Fixed: 0.840 on 50 docs.

### 8.2 The `unknown seizure type` problem is structural

The consistent 13–15 misses across all models (4B–35B) and all harnesses means:
- Scale will not solve this.
- Better prompts will not solve this (H6fs, H6ev, H6qa all show the same count).
- The only solutions are: (a) change the annotation protocol to accept inferred types, or (b) treat this as a known benchmark limitation.

**Dissertation framing:** This is not a failure of clinical extraction. It is a mismatch between model behavior (probabilistic inference) and annotation protocol (conservative abstention).

### 8.3 What is a valid claim?

A model output should be considered correct when:
1. It is semantically equivalent to the gold under clinical normalization.
2. It is supported by verbatim evidence in the source letter.
3. Any deviation from gold is due to granularity difference (more specific or more general), not factual error.

The corrected scorer (Phase 2) implements criteria 1 via collapsed labels and ASM synonyms. Evidence grounding (quote validity ≥0.960) implements criterion 2. Granularity differences should be reviewed manually, not penalized automatically.

---

## 9. Synthesis

The gold standard analysis reveals that **measurement validity is as important as model capability.** The original dissertation plan assumed the gold standard was authoritative. The recovery oracle and subsequent audits showed that:

1. **29.2% of ExECTv2 frequency is unscoreable** even with perfect extraction.
2. **13.3% of seizure type is ambiguous** due to annotation gaps and meta-label semantics.
3. **10.8% of medication tuples are underspecified** in the gold.
4. **Clinical accuracy often exceeds gold-string accuracy** — models extract correct clinical facts in different words.

These findings do not invalidate the project. They **refine** the claims:
- Medication extraction is robust and approaches clinical utility.
- Seizure type extraction is limited by benchmark design, not model capability.
- Frequency claims belong on Gan, where the gold supports normalization.
- Evidence grounding (quote validity) is a stronger safety signal than F1 alone.

---

*Document compiled from: `docs/_master_timeline_and_narrative.md`, `docs/34_full_experiment_record.md`, `docs/28_gold_label_quality_analysis.md`, `docs/30_gold_audit_results.md`, `docs/31_gold_qualitative_analysis.md`, `docs/33_gold_audit_synthesis.md`, `docs/37_clinical_accuracy_vs_gold_standard_tension.md`, `docs/38_gold_standard_quality_audit.md`, and ExECTv2 JSON entities.*
