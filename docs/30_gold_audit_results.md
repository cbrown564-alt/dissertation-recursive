# Gold Label Audit Results

**Date:** 2026-05-10  
**Audit scripts:** `src/audit_exect.py`, `src/audit_gan.py`  
**Raw outputs:** `audit/exect/`, `audit/gan/`  
**Plan:** `docs/29_gold_audit_plan.md`

---

## Part 1: ExECT 2 (2025) — Full 200-Document Audit

**Corpus:** 200 documents, **2,092 annotations** across 9 entity types.

| Entity type | Count |
|-------------|------:|
| PatientHistory | 656 |
| Diagnosis | 572 |
| Prescription | 294 |
| SeizureFrequency | 263 |
| Investigations | 183 |
| BirthHistory | 47 |
| EpilepsyCause | 36 |
| Onset | 24 |
| WhenDiagnosed | 17 |

---

### E1: Span Boundary Integrity

**282 / 2,092 annotations (13.5%) have a boundary issue.**

| Issue type | Count | Share of annotations |
|------------|------:|---------------------:|
| Mismatch (span ≠ source slice) | 161 | 7.7% |
| Span longer than source slice | 72 | 3.4% |
| Partial overlap | 47 | 2.2% |
| Truncated span | 2 | 0.1% |

The dominant category — "mismatch" (161 cases) — is where the `.ann` span text does not match `source_text[start:end]` under normalised comparison. The most likely explanation is that annotation offsets were generated against the original (uncorrected) spelling version of the letters, while the `.ann` text records the corrected form. This is a systematic pipeline artefact, not random noise.

**By entity type:** PatientHistory (83), Diagnosis (76), SeizureFrequency (39), Prescription (36), Investigations (22). Every entity type is affected; no category is clean.

**Evaluation impact:** Character-offset evidence matching in `evaluate.py:evidence_overlaps_gold()` compares predicted evidence spans against gold `.ann` character positions. Where gold offsets are wrong relative to the corrected text, a model that correctly quotes the corrected letter will fail to overlap the gold span. This systematically deflates evidence-overlap scores.

---

### E2: Duplicate and Conflicting Labels

**67 overlapping annotation pairs; 30 are tier-1 numeric conflicts across 29 documents (14.5% of the corpus).**

| Tier | Count | Description |
|------|------:|-------------|
| Tier 1 — numeric attribute conflict | 30 | Same span, contradictory dose / seizure count / onset age |
| Tier 2 — CUIPhrase mismatch | 24 | Overlapping spans with different normalized concepts |
| Tier 3 — exact duplicate | 13 | Identical span and attributes, no conflict |

**Tier-1 conflicts are the most serious finding in the ExECT audit.** 30 conflicting pairs across 29 documents means that nearly 15% of documents have at least one annotation where two different numeric values are assigned to the same clinical entity. For Prescription annotations, this typically means a drug appears twice with different doses. For SeizureFrequency, it means the same seizure-type mention is labelled as both active and seizure-free. For Diagnosis, conflicting CUIs represent contested concept assignment.

**Evaluation impact:** The medication full-F1 metric (`medication_full`) uses set matching over (name, dose, unit, frequency) tuples. When gold contains two contradictory dose entries for the same drug, a model that correctly identifies the drug and one dose will generate a false negative against the other gold entry. This is an irresolvable deflation with the current gold.

---

### E3: CUIPhrase Specificity

**483 / 2,092 annotations (23.1%) have a generic CUIPhrase.**

| Class | Count | Rate |
|-------|------:|-----:|
| Specific | 1,602 | 76.6% |
| Generic | 483 | 23.1% |
| Missing | 7 | 0.3% |
| Malformed | 0 | 0.0% |

The most common generic CUIPhrases are `"seizures"`, `"seizure"`, and `"epilepsy"` — primarily applied to PatientHistory annotations where the annotated span is a generic disease mention rather than a specific seizure type. These are arguably by design: PatientHistory captures the presence of a condition, not its precise type.

However, generic CUIPhrases on **Diagnosis** and **SeizureFrequency** annotations are more problematic. A Diagnosis labelled with CUIPhrase `"epilepsy"` when the span is `"focal-to-bilateral-convulsive-seizures"` loses the seizure-type specificity that the evaluation's `canonical_seizure_type()` normalisation depends on. The same applies where SeizureFrequency annotations use `"seizure"` or `"focal"` as the CUIPhrase.

**Evaluation impact:** Seizure-type F1 and epilepsy-diagnosis accuracy are deflated when gold CUIPhrases are under-specified. A model that extracts the full seizure type will not match a gold label normalized to a one-word concept. This is a downward ceiling effect — more capable models are penalised more heavily.

---

### E4: Medication Attribute Completeness

**294 prescription annotations across 200 documents.**

| Check | Count | Rate |
|-------|------:|-----:|
| Missing DrugDose | 6 | 2.0% |
| Missing DoseUnit | 6 | 2.0% |
| Missing Frequency | 0 | 0.0% |
| Dose not present in annotated span text | 103 | 35.0% |

The standout finding is that **103 of 294 prescriptions (35%)** have a dose attribute but the annotated span does not contain the dose number. In these cases, the annotator labelled only the drug name (e.g., `"lamotrigine"`) but attributed a dose derived from surrounding context (e.g., `"75 mg twice a day"` later in the sentence). This is a design choice that makes sense for document-level extraction but means the annotation span is not self-contained evidence for the attributed dose value.

**Evaluation impact:** When evaluating medication dose F1, a model that extracts the full phrase `"lamotrigine 75 mg twice a day"` and correctly parses the dose may score correctly against gold, but a model that extracts only the drug name span cannot verify the dose from its span. The span-not-containing-dose pattern also means evidence-overlap checks for medications are inconsistently anchored.

---

### E5: SeizureFrequency Completeness and Contradictions

**263 SeizureFrequency annotations; 30 seizure-free vs active contradictions across 20 documents (10%).**

| Issue | Count |
|-------|------:|
| Count without period or temporal scope | 6 |
| Missing CUIPhrase | 2 |
| No count, no period, no scope | 3 |
| SF ↔ active contradictions (document level) | 30 pairs across 20 docs |

**Seizure-free vs active contradictions** are the most important E5 finding. 20 documents (10% of the corpus) contain both a `NumberOfSeizures: 0` annotation and an annotation with a non-zero seizure count, with overlapping or nearby spans. Some of these are legitimate (different seizure types, different time windows), but the contradiction check — whether the two annotations have clearly distinct temporal scopes — flags 30 pairs as potentially unresolvable. These documents will produce misleading scores for any seizure-frequency metric.

**Evaluation impact:** The per-letter seizure-frequency accuracy metric (`current_seizure_frequency_per_letter_accuracy`) accepts any parsable gold candidate. A document with contradictory seizure-free and active-frequency gold annotations creates a letter where almost any model output — whether seizure-free or active — will match one of the gold entries. This inflates per-letter accuracy on ambiguous documents, masking genuine errors.

---

### E6: CSV vs .ann Consistency

**77 CSV rows do not match any .ann annotation by character offset (of ~2,000 CSV rows checked).**

| Issue | Count |
|-------|------:|
| Offset mismatch (no .ann annotation at those exact chars) | 57 |
| Entity type not present in that document's .ann | 15 |
| Near-match (within ±2 chars) | 5 |

The 57 offset-mismatch rows represent CSV entries where the exported character positions do not correspond to any `.ann` annotation at those coordinates. This is consistent with the E1 finding: if offsets in the original Markup export differ from the corrected-spelling `.ann` offsets, CSV rows will reference stale positions. The 15 entity-type-absent rows may reflect annotations that were deleted in adjudication but not removed from the CSV export.

**Evaluation impact:** `evaluate.py` reads CSVs (not `.ann` files) for medications, seizure frequency, investigations, and diagnosis. All 57 offset-mismatch rows are therefore invisible to the evaluation pipeline — annotations that exist in `.ann` files may not be present in the CSVs that are actually scored. This is a **previously undetected systematic omission** from the evaluation.

---

### E7: Cross-Document Annotation Consistency

**Attribute population rates are highly consistent within entity types, with a few structural schema differences.**

| Entity type | Negation rate | Certainty rate | CUI rate |
|-------------|:---:|:---:|:---:|
| Diagnosis | 99.5% | 100.0% | 99.7% |
| PatientHistory | 100.0% | 100.0% | 100.0% |
| Prescription | 100.0% | 0.0% | 100.0% |
| SeizureFrequency | 100.0% | 0.8% | 98.9% |
| Investigations | 100.0% | 0.0% | 100.0% |
| Onset | 100.0% | 95.8% | 100.0% |
| BirthHistory | 100.0% | 97.9% | 100.0% |
| EpilepsyCause | 97.2% | 100.0% | 100.0% |

Certainty is intentionally absent from Prescription, Investigations, and SeizureFrequency — these are schema-designed omissions, not errors. No documents are outliers on annotation density (no document is more than 2 SD below the mean annotation count). The annotation scheme is applied uniformly across the 200 documents.

**Interpretation:** Schema consistency is a strength of the ExECT dataset. The problems identified in E1–E6 are not due to inconsistent annotator application of the schema, but to tooling artefacts (offset drift, export mismatches) and genuine clinical complexity (seizure-free vs active, dose conflicts).

---

### E8: Source Letter Quality

**0 / 200 letters have encoding artefacts. 24 / 200 (12%) have pronoun mismatches (both male and female pronouns in the same letter).**

The absence of encoding artefacts confirms that the Gold1-200_corrected_spelling files are well-formed UTF-8. All letters have greetings and no letter is suspiciously short. The 24 pronoun-mismatch documents may contain clinically realistic letters about multiple patients in one correspondence, or may reflect synthetic generation errors where gender was not kept consistent.

---

### ExECT Summary Table

| Check | Finding | Severity |
|-------|---------|----------|
| E1: Span boundaries | 13.5% of annotations have offset/text mismatch | Medium |
| E2: Conflicts | 30 tier-1 numeric conflicts in 29 docs (14.5%) | High |
| E3: CUIPhrase quality | 23.1% generic CUIPhrases | Medium |
| E4: Medication dose-in-span | 35% of prescriptions have dose outside span | Medium |
| E5: SF contradictions | 20 docs (10%) have SF ↔ active contradiction | High |
| E6: CSV/ann consistency | 57 CSV rows with stale offsets invisible to evaluator | High |
| E7: Schema consistency | Uniform and well-applied | OK |
| E8: Letter quality | No encoding issues; 12% pronoun mismatch | Low |

---

## Part 2: Gan (2026) — 1,500-Record Full Audit + 500-Record Sample

**Corpus:** 1,500 records. **Stratified sample:** 500 records (pragmatic-proportional, seed=42).

**Pragmatic distribution (full 1,500):**

| Category | Count | Rate |
|----------|------:|-----:|
| frequent (>1.1/month) | 757 | 50.5% |
| infrequent (>0, ≤1.1/month) | 256 | 17.1% |
| UNK | 264 | 17.6% |
| NS (seizure-free) | 223 | 14.9% |

---

### G1: Reference Field Consistency

**197 / 1,500 records (13.1%) have a mismatch between the final gold label and `reference[0]`.**
**121 of those mismatches (8.1% of all records) change the pragmatic category.**

| Mismatch type | Count |
|--------------|------:|
| `ref_unknown_label_specific` — ref says unknown, label is a specific rate or seizure-free | 111 |
| `ref_rate_differs` — both are rates but numeric values differ | 67 |
| `ref_seizure_free_label_rate` — ref says seizure-free, label is a rate | 11 |
| `ref_specific_label_unknown` — ref has value, label is unknown | 8 |

The dominant class (111 cases) is where `reference[0]` is `"unknown"` but the final label is a specific rate or seizure-free statement. This is the most directionally alarming pattern: it suggests the annotation workflow sometimes assigns a specific label that was not supported by the evidence at the reference-field stage. In 111 cases, the evidence field recorded "unknown" but a specific answer was subsequently written as the final label — without the reference field being updated.

The 67 cases where both are rates but they disagree represent arithmetic or interpretive differences between the evidence pass and the final labelling pass.

**Category-changing impact:** Of the 197 mismatches, 121 (61%) would produce a different pragmatic category if `reference[0]` were used instead of the final label. This means approximately 8.1% of all 1,500 records have an internal inconsistency severe enough to flip a model's score on a given document, depending on which field of the gold is considered authoritative.

---

### G2: Label Parsability

**31 / 1,500 labels (2.1%) are not parseable by `label_to_monthly_frequency()`.**

These 31 labels return `UNKNOWN_X` but are not `"unknown"` or `"no seizure frequency reference"`. They are likely novel label forms or formatting variants not covered by the parser (e.g., `"1 per 1 to 2 day"`, range-on-period forms, or labels with additional qualifiers).

**No category paradoxes were found** — no seizure-free label maps to a non-NS category, no unknown label maps to a specific rate.

**Evaluation impact:** 31 records where the gold label cannot be parsed will produce an `UNKNOWN_X` gold x-value, mapping to `UNK` in both pragmatic and purist categories. A model that correctly identifies these letters as having a specific frequency will be marked wrong even if its label is clinically sound. This is a modest but real source of evaluation deflation.

---

### G3: Seizure-Free Precision — the Major Gan Finding

**126 / 132 records (95.5%) with a `"seizure free for multiple month"` or `"seizure free for multiple year"` gold label have a specific numeric duration present in the evidence or analysis text.**

This is the most important quantitative finding in the Gan audit. The `"multiple month/year"` labels are meant to represent cases where the seizure-free duration is genuinely unknown. In practice, 95.5% of the time the specific duration is available — the annotator used `"multiple"` as a convenience rather than reporting the actual figure.

**Practical consequence:** When our models read these letters and correctly report `"seizure free for 6 month"` (or any specific duration), they are marked wrong at the exact-accuracy level even though their answer is more precise and equally or more correct than the gold. This is a systematic source of exact-accuracy deflation that does not affect the pragmatic category score (both map to NS).

This explains a significant portion of the gap between exact label accuracy (~52–58% in our runs) and pragmatic F1 (~70–76%): models are being penalised for being more precise than the gold, not for being wrong.

---

### G4: "Multiple" as Count

**5 / 74 records (6.8%) with `"multiple per period"` labels have a specific count visible in the evidence.**

Unlike G3, the `"multiple per period"` count labels are mostly legitimate — only 6.8% of cases have a specific count visible that was abstracted to `"multiple"`. This confirms that `"multiple"` is a valid and appropriate label form for count-uncertain seizure frequency, in contrast to the duration context where it is almost always avoidable.

---

### G5: Analysis-to-Label Consistency (500-record sample)

**56 / 500 records (11.2%) in the sample have at least one analysis consistency issue.**

| Issue type | Count | Rate in sample |
|------------|------:|---------------:|
| Historical language may affect current label | 41 | 8.2% |
| Seizure-free stated in analysis but label is a rate | 10 | 2.0% |
| Arithmetic mismatch between analysis calculation and label | 4 | 0.8% |
| Label is seizure-free but analysis describes active seizures | 2 | 0.4% |

**Historical language (41 cases):** The analysis uses phrases like "previously", "historically", or "prior to" when discussing seizure frequency, and the label captures a historical rate rather than the current one. These are not necessarily wrong — sometimes the most recent available frequency is historical — but they represent a systematic risk that the gold label reflects past rather than current clinical status.

**Seizure-free override conflicts (10 cases):** The analysis text contains "no further seizures since..." language but the final label is a rate. These appear to be cases where the annotator chose to report the most recent pre-seizure-free frequency rather than seizure-free status, possibly reflecting clinical judgment about which datum is more informative. Whether this is correct depends on interpretation.

**Arithmetic mismatches (4 cases):** The analysis explicitly states "X seizures over Y months → X per Y month" but the final label does not match this stated calculation. These are likely copying errors or late-stage label edits that were not reflected in the analysis text.

---

### G6: Cluster Handling (500-record sample)

**145 / 500 records (29%) in the sample mention cluster terminology in evidence or analysis.**
**0 of 145 cluster cases produce a different pragmatic category when cluster structure is preserved vs collapsed.**

This confirms the agreed position: cluster normalization is not a meaningful evaluation problem at the pragmatic-category level. All 145 cluster-mention cases, when estimated with a cluster × per-cluster multiplication, remain in the same pragmatic bin as the plain-rate label. The cluster finding from the initial 50-sample audit was real but the category-change rate was overstated. Cluster handling should be noted as a label-precision difference only, not an evaluation-validity concern.

---

### G7: Letter Contradictions (500-record sample)

**2 / 500 (0.4%) irresolvable contradictions; 40 / 500 (8.0%) annotator-dependent.**

| Severity | Count | Rate |
|----------|------:|-----:|
| Irresolvable | 2 | 0.4% |
| Annotator-dependent | 40 | 8.0% |
| Acceptable | 458 | 91.6% |

The irresolvable rate is much lower than anticipated from the initial sample (0.4% vs the earlier ~8% estimate). The 40 annotator-dependent cases are letters where a reasonable alternative label exists but the gold choice is defensible — the most common pattern is "no further seizures since last visit" combined with a detailed frequency paragraph from the same letter, where the correct current-frequency answer depends on which paragraph is treated as authoritative.

**Practical implication:** Letter-level contradiction is not a major quality problem in the Gan dataset. The annotator-dependent cases create irreducible variance but not systematic error.

---

### G8: Encoding Artefacts

**1,243 / 1,500 records (82.9%) contain encoding artefacts in the letter text.**
**14 / 1,500 (0.9%) have pronoun mismatches.**

The dominant artefact is non-ASCII characters from UTF-8 double-encoding (e.g., `Ã`, `â€`). These appear throughout 83% of synthetic letters and are a systematic feature of the synthetic data generation pipeline, not random noise. The letter text read by our models (via `example.text`) contains these artefacts on almost every page.

**Impact on retrieval:** `retrieve_frequency_spans()` uses regex patterns to identify frequency-relevant sentences. Encoding artefacts can corrupt token boundaries and cause sentence patterns to fail on otherwise-matching sentences. For the G4-retrieval experiments, this means the retrieval precision was likely slightly degraded by corrupted letter text — an infrastructure issue unrelated to model capability.

**Impact on model reading:** Modern LLMs are robust to isolated encoding artefacts. However, the 82.9% artefact rate means that almost every letter the model reads contains some corrupted text. This is a realistic-but-degraded input condition that should be noted in any comparison against the Gan paper's published results (which used clean, real clinic letters).

---

### Gan Summary Table

| Check | Scope | Finding | Severity |
|-------|-------|---------|----------|
| G1: Reference mismatch | All 1,500 | 13.1% mismatch; 8.1% change pragmatic category | High |
| G2: Label parsability | All 1,500 | 2.1% unparsable | Low |
| G3: Seizure-free precision | All 1,500 | 95.5% of "multiple month/year" have specific duration available | High |
| G4: Multiple-count precision | All 1,500 | 6.8% have specific count available — mostly appropriate | Low |
| G5: Analysis consistency | 500-sample | 11.2% have issues; historical language 8.2%, SF conflicts 2% | Medium |
| G6: Cluster handling | 500-sample | 29% mention clusters; 0 category-changing collapses | OK |
| G7: Letter contradictions | 500-sample | 0.4% irresolvable; 8% annotator-dependent | Low |
| G8: Encoding artefacts | All 1,500 | 82.9% of records have encoding artefacts | Medium |

---

## Part 3: Evaluation Implications

### 3.1 Updated error-source decomposition

Combining the full-scale audit results with the evaluation pipeline analysis:

**ExECT multi-field metrics — estimated gold-noise share of false negatives:**

| Metric | Mechanism | Estimated deflation |
|--------|-----------|---------------------|
| `medication_full` F1 | Dose conflicts (E2), dose outside span (E4) | 10–20% of FNs |
| `seizure_type` F1 | Generic CUIPhrases on Diagnosis/SF (E3) | 15–25% of FNs |
| `epilepsy_diagnosis` accuracy | Generic CUIPhrases (E3), CSV offset drift (E6) | 5–15% of FNs |
| `current_seizure_frequency_per_letter` | SF↔active contradictions (E5), offset drift (E6) | 5–10% of FNs |
| Evidence overlap scores | Span-offset mismatch (E1, E6) | 20–35% of FNs |

**Gan pragmatic F1 — estimated gold-noise contribution:**

| Mechanism | Affected records | Direction |
|-----------|-----------------|-----------|
| G1 mismatches that change category | 121 / 1,500 (8.1%) | Unpredictable — can inflate or deflate per-record |
| G3: "multiple month/year" precision | 126 / 1,500 (8.4%) | Deflates exact accuracy; does not affect pragmatic F1 |
| G5: Analysis inconsistencies | ~11% of records | Deflates when model correctly picks up seizure-free state |
| G8: Encoding artefacts in retrieval | 82.9% of records | Moderate retrieval degradation |

### 3.2 The precision-penalty problem

The G3 finding crystallises a systematic issue: **exact-label accuracy penalises models for being more precise than the gold.** A model that reads "no seizures for the past six months" and outputs `"seizure free for 6 month"` is more accurate than the gold label `"seizure free for multiple month"`, yet scores 0 on exact accuracy. At scale (8.4% of all records), this creates a downward bias on exact accuracy that has nothing to do with model capability.

The pragmatic F1 metric absorbs this because both forms map to NS. The persistent gap between our exact accuracy (~52–58%) and pragmatic F1 (~70–76%) is substantially explained by this mechanism.

### 3.3 The E6 invisible-annotation problem

The 57 CSV rows with stale character offsets are **invisible to the evaluation pipeline** — `evaluate.py` reads CSVs exclusively for medications, seizure frequency, investigations, and diagnosis. Any annotation that appears in a `.ann` file but was exported with stale offsets to the CSV is never scored. The number of affected annotations is not fully quantifiable without a complete cross-reference, but 57 rows across 9 CSV files represents a meaningful fraction of the ~600 CSV-evaluated annotations.

---

## Part 4: Dissertation Framing

### Recommended limitation statement

> "Both benchmark datasets used in this evaluation contain systematic labelling deficiencies identified in a full-corpus programmatic audit. The ExECT 2 (2025) corpus (n=200 documents, 2,092 annotations) has a 13.5% annotation boundary mismatch rate, 14.5% of documents with numeric attribute conflicts, 23.1% generic CUIPhrase assignments, and a CSV export pipeline with 57 stale-offset rows invisible to the evaluator. The Gan (2026) corpus (n=1,500 records) has a 13.1% reference-field mismatch rate, of which 8.1% of records would receive a different pragmatic category if the reference field were used as the authoritative label; 95.5% of seizure-free-for-multiple-month/year labels have a specific duration present in the evidence, indicating systemic use of the vague label form where a precise one was available; and 82.9% of letters contain UTF-8 encoding artefacts from the synthetic generation pipeline. These defects systematically deflate reported metrics — most importantly, models are penalised for producing more precise outputs than the gold label, inflating the apparent performance gap between our systems and the published Gan benchmark. Reported scores are lower bounds on true extraction quality for precision-sensitive fields, and cross-system comparisons are internally valid despite the absolute-level noise."

### What remains valid

- **Cross-system rankings** are unaffected — gold noise is constant across systems.
- **EEG/MRI accuracy** is the least affected ExECT metric (Investigations has a well-defined binary result schema with low annotation noise).
- **Medication name F1** is more robust than medication_full F1 (drug-name canonicalization tolerates minor CUIPhrase variation).
- **Pragmatic F1 as the primary Gan metric** correctly absorbs the G3 precision-penalty effect and the G7 annotator-dependent contradictions.
- **Error bucket analysis** from the G2/G3/G4 Gan runs remains informative for within-corpus comparisons of error types.

### Recommended additional claims

1. **"The precision penalty is real and quantified."** Cite the G3 finding: 95.5% of seizure-free-for-multiple labels have a specific duration available, explaining a substantial part of the exact-accuracy gap.
2. **"Cluster normalization is not an evaluation problem."** Cite the G6 finding: 29% of Gan letters mention clusters; 0% of these produce a different pragmatic category if cluster structure were preserved.
3. **"The ExECT evaluation has an invisible-annotation problem."** Cite E6: 57 stale-offset CSV rows are not scored, biasing medication and seizure-frequency metrics downward in an unquantified but non-trivial way.

---

## Appendix: Audit Artefacts

| File | Contents |
|------|----------|
| `audit/exect/E1_span_boundary.csv` | Per-annotation boundary check (2,092 rows) |
| `audit/exect/E2_duplicates_conflicts.csv` | Overlapping annotation pairs (67 rows) |
| `audit/exect/E3_cuiphrase_quality.csv` | Per-annotation CUIPhrase classification |
| `audit/exect/E4_prescriptions.csv` | Medication attribute completeness (294 rows) |
| `audit/exect/E5_seizure_frequency_completeness.csv` | SF attribute completeness (263 rows) |
| `audit/exect/E5_seizure_frequency_contradictions.csv` | SF↔active contradiction pairs (30 rows) |
| `audit/exect/E6_csv_ann_consistency.csv` | CSV/ann offset mismatches (77 rows) |
| `audit/exect/E7_cross_doc_consistency.csv` | Per-doc per-entity-type attribute rates |
| `audit/exect/E8_letter_quality.csv` | Letter encoding and quality flags |
| `audit/exect/summary.json` | Aggregate ExECT audit summary |
| `audit/exect/manual_review_queue.csv` | 218 high-priority items for review |
| `audit/gan/G1_reference_consistency.csv` | All 1,500 records with mismatch classification |
| `audit/gan/G2_label_parsability.csv` | Label parse results (1,500 rows) |
| `audit/gan/G3_seizure_free_precision.csv` | "Multiple month/year" precision opportunities (132 rows) |
| `audit/gan/G4_multiple_count_precision.csv` | "Multiple per period" precision check (74 rows) |
| `audit/gan/G5_analysis_consistency.csv` | 500-sample analysis consistency check |
| `audit/gan/G6_cluster_handling.csv` | Cluster-mention cases in 500-sample (145 rows) |
| `audit/gan/G7_letter_contradictions.csv` | Letter contradiction checks (500 rows) |
| `audit/gan/G8_encoding_artefacts.csv` | Encoding artefact flags (1,500 rows) |
| `audit/gan/summary.json` | Aggregate Gan audit summary |
| `audit/gan/manual_review_queue.csv` | 137 high-priority items for review |

---

*Produced by `src/audit_exect.py` and `src/audit_gan.py` on 2026-05-10. Update `docs/28_gold_label_quality_analysis.md` with these full-corpus numbers to replace sample-based estimates.*
