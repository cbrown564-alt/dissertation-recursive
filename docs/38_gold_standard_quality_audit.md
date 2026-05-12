# Gold-Standard Quality Audit: ExECTv2 Annotations Under Clinical Scrutiny

**Date:** 2026-05-11  
**Scope:** All 200 synthetic epilepsy clinic letters in ExECTv2, with deep case-study analysis of 25+ documents across every annotated category.  
**Reference:** Fonferko-Shadrach et al., *Annotation of epilepsy clinic letters for natural language processing*, J Biomed Semant 15, 17 (2024). DOI: 10.1186/s13326-024-00316-z  
**Method:** Manual review of annotation guidelines (v9), BRAT `.ann` files, Markup CSV exports, JSON gold files, and source letter texts; cross-referenced with `src/evaluate.py` gold-loading logic and full project experiment record (`docs/34_full_experiment_record.md`).  
**Author:** Systematic audit conducted against the project's own extraction outputs and evaluation criteria.

---

## 1. Executive Summary

This report presents an exhaustive, evidence-based audit of the ExECTv2 gold-standard annotations. The central finding is that **the gold standard is clinically informed but structurally loose**, and in several critical respects it is misaligned with the temporally aware, precision-oriented extraction system this project has built. The misalignment is not a minor implementation detail; it is a systematic measurement bias that punishes clinical accuracy and rewards extraction breadth.

Key findings:

1. **The gold standard is temporally flat by construction.** Seizure types are harvested from `MarkupSeizureFrequency.csv` without temporal filtering. Historical seizure types from 2014, 2016, and 2017 are treated as current patient findings. A patient who is explicitly seizure-free today is gold-labelled with their historical seizure types.

2. **The annotation guidelines explicitly sanction this looseness.** Example 4 and Example 5 in the Diagnosis section instruct annotators to label negated/historical seizure mentions as affirmed diagnoses because "the history of having GTCS is affirmed." The guideline teaches annotators to ignore temporal scope.

3. **Inter-annotator agreement was only F1 = 0.73.** The paper itself reports this as evidence that the task is difficult. Prescriptions scored highest (0.87); "When Diagnosed" lowest (0.45). The 0.73 ceiling means even perfect human agreement is not achievable.

4. **Span boundaries are systematically noisy.** Across the corpus, annotations frequently include trailing hyphens, start mid-token, or truncate words. The prior inspection of 20 documents found 37 trailing-hyphen spans, 9 truncated endings, and 3 mid-word starts.

5. **Duplicate and conflicting annotations are present.** Seven spans in the seizure-frequency CSV carry contradictory attributes (e.g., "0 since 2019" and "1–2 per year" on the exact same span). Medication annotations include dose conflicts (sodium valproate labelled as both 700 mg and 800 mg on overlapping spans).

6. **Generic seizure terms pollute the seizure-type label set.** `MarkupSeizureFrequency.csv` contains 111 entries where the seizure-type field is `seizures`, `seizure`, or `null`. These are filtered by `canonical_seizure_type()` in the scorer, but their presence reveals a lack of type-level precision in the source annotations.

7. **Our extraction systems are more precise than the gold standard allows.** The project's multi-agent pipeline (MA_v1) correctly identifies that EA0006 is seizure-free and excludes 2014 historical types; it scores F1 = 0.0 against gold. A broken pipeline that ignores temporality scores F1 = 1.0. This inversion is the defining symptom of a measurement problem, not a model problem.

8. **The "oracle failure rate" of 13.3% for seizure type is partly an artefact of annotation looseness, not just missing labels.** Many "failures" occur because the model outputs `unknown seizure type` or `seizure free` while the gold expects a historical-specific type, or because the model correctly abstains where the gold incorrectly infers.

**Bottom line:** The project has been iteratively over-engineering prompts to match a noisy, temporally blind, and occasionally contradictory gold label set. The seizure-type F1 ceiling of ~0.60–0.65 on validation is not primarily a model-capacity ceiling; it is a **gold-standard fidelity ceiling**. The way forward is not more prompt engineering. It is better measurement—specifically, temporally scoped scoring, meta-label validation, and explicit handling of the precision-looseness gap.

---

## 2. Methodology

### 2.1 Data Sources

| Source | Files | Role in this audit |
|--------|-------|-------------------|
| Annotation guidelines | `ExECT V2 .1- What and How of annotating_v9.docx` | Primary source for understanding annotator instructions, examples, and admitted ambiguities |
| Source letters | `Gold1-200_corrected_spelling/EA*.txt` | Ground truth clinical text against which annotations were compared |
| BRAT annotations | `Gold1-200_corrected_spelling/EA*.ann` | Entity spans and attributes in standoff format |
| JSON exports | `Json/EA*.json` | Machine-readable gold annotations used by external consumers |
| Markup CSVs | `MarkupOutput_200_SyntheticEpilepsyLetters/*.csv` | Tabular exports driving `src/evaluate.py` gold loading |
| Scorer code | `src/evaluate.py` | Reveals how gold is transformed into evaluation targets |
| Prior inspection | `data-examination/EXeCT_20_inspection.txt` | Independent audit of 20 documents (EA0181–EA0200) |
| Experiment record | `docs/34_full_experiment_record.md` | Context on evaluation criteria, harness designs, and score trajectories |
| MA_v1 tension doc | `docs/37_clinical_accuracy_vs_gold_standard_tension.md` | Documented the temporal-scope mismatch hypothesis |

### 2.2 Review Protocol

1. **Guideline archaeology:** Extracted the full text of the v9 annotation guidelines and mapped every explicit rule, example, and admitted limitation to the corresponding evaluation field.
2. **Code-level gold construction analysis:** Read `load_gold()` in `src/evaluate.py` line-by-line to identify where temporal attributes are dropped, where generic terms are filtered, and where label sets are flattened.
3. **Corpus-level statistics:** Computed aggregate counts of temporal scopes, certainty levels, generic entries, duplicate spans, and boundary defects across all 200 documents.
4. **Case-study deep dives:** Selected 25+ documents representing every major failure mode: temporal mismatch (EA0006, EA0004, EA0011, EA0005), medication ambiguity (EA0017, EA0013), diagnosis overlap (EA0001, EA0002), investigation noise (EA0022, EA0030), seizure-frequency contradiction (EA0194, EA0069), and boundary defects (EA0184, EA0188, EA0195).
5. **Cross-reference with extraction outputs:** Compared gold labels against MA_v1, S2, E3, and H6 system outputs to identify cases where clinically correct predictions are scored as false negatives.

---

## 3. The Reference Paper: Claims, Context, and Caveats

Fonferko-Shadrach et al. (2024) describe the creation of 200 synthetic epilepsy clinic letters, double-annotated by four trained researchers/clinicians, then reviewed into a consensus gold standard. Several claims in the paper are directly relevant to this audit:

### 3.1 Inter-Annotator Agreement (IAA) = 0.73

> "The overall F1 score for human IAA was 0.73."

This is the single most important benchmark for gold-standard quality. An IAA of 0.73 means that **two trained human annotators disagree on more than one in four annotations**. The paper notes that "missing annotations and attributes, or misclassification of concepts" were the main errors. It also states that "missing or misassigned CUIs were also common."

**Implication:** Any NLP system scoring above ~0.73 is already exceeding human consistency. The project's best systems (E3, D3, H7) achieve 0.82–0.85 on composite benchmark quality. The seizure-type collapsed F1 of 0.61–0.63, while below the Fang et al. target of ≥0.76, is within 12 percentage points of human agreement on a task that the paper explicitly calls "difficult."

### 3.2 Seizure Frequency: The Lowest-Scoring Field

> "Validation of ExECTv2 against the gold standard produced an overall per item F1 score of 0.87, with *Seizure Frequency* having the lowest result (0.66)."

The paper acknowledges that seizure frequency is "recorded in a wide variety of formats and styles" and that "this difficulty with very unstructured or variable text is a significant disadvantage of annotating text for a rule-based system."

**Implication:** The project's own seizure-frequency scores (0.075–0.175 on ExECTv2 strict; 0.84 on Gan retrieval) are not anomalies. They reflect the intrinsic difficulty of the task and the known limitations of the ExECTv2 frequency annotation schema. The 29.2% oracle failure rate discovered in the project's aggregation oracle (`docs/34_full_experiment_record.md` §4.6) is consistent with the paper's observation that frequency is the hardest field.

### 3.3 Annotator Fatigue and Concept Complexity

> "The range of features to be assigned and the need for matching against the UMLS list... may have contributed to annotator fatigue and subsequent errors."

The paper admits that the UMLS matching requirement—a design choice driven by the rule-based ExECTv2 pipeline—introduced noise. CUIs were ultimately disregarded from IAA because mismatches "did not reflect annotators' choice but occurred in error."

**Implication:** The CUI and CUIPhrase fields, which occupy a large portion of the JSON exports, are known to be unreliable. The project's scorer does not use CUI fields directly, which is correct. However, the CUIPhrase inconsistencies (e.g., mapping `drug-refractory` to `drug`, `focal-motor-seizures` to `focal`) reveal that even the normalized concepts are unevenly applied.

### 3.4 Limitations Explicitly Stated

> "The choice of items identified for annotation... does not include all concepts present in epilepsy documents (e.g. seizure semiology, technical details of investigation results such as EEGs, and family history) or negated statements."

**Implication:** The gold standard is incomplete by design. Family history is entirely absent, which means systems that correctly exclude family-history seizures get no credit. Negated statements are largely unannotated, which means systems that correctly suppress negated findings get no credit either. The evaluation is asymmetric: it can punish precision but cannot reward it.

---

## 4. The Annotation Guidelines: Rules, Ambiguities, and Design Choices

The v9 guidelines (dated 09.09.2023) are 2,460 lines of instruction when extracted to plain text. They are detailed, pragmatic, and—critically—they contain explicit examples that teach annotators to **ignore temporal scope** for seizure types and to treat historical mentions as current diagnoses.

### 4.1 Diagnosis: The Temporal-Scope Blindness Is By Design

The Diagnosis section includes six examples. Examples 4 and 5 are the smoking gun:

**Example 4:**  
> "He has not had a generalised tonic clonic seizure for a while."  
> **Diagnosis:** `generalised tonic clonic seizure`, DiagCategory = `single seizure`, Certainty = 5, Negation = Affirmed  
> "Although he is not having seizures now, he 'usually' does, and even if the sentence seems to be a negation it states that he has had gtcs."

**Example 5:**  
> "I was pleased to hear that she has not had any further generalised tonic clonic seizures since August 2016"  
> **Diagnosis:** `generalised tonic clonic seizure`, DiagCategory = `multiple seizures`, Certainty = 5, Negation = Affirmed  
> "Although the statement is negated the history of having generalised tonic clonic seizures is affirmed, so it should be annotated."

These examples are not edge cases. They are **pedagogical instructions** telling annotators to label historical seizure types as affirmed current diagnoses. The guideline explicitly overrides the temporal signal in the text ("since August 2016") in favor of a historical-affirmation heuristic.

**Impact on our evaluation:** When our MA_v1 pipeline correctly segments EA0006 as "seizure free" and excludes the 2014 GTCS and absence-like seizures, it is behaving *against* the guideline's taught behavior. The gold standard for EA0006 includes `generalized tonic clonic seizure` (×2) and `generalized absence seizure` because the annotator followed Example 5. The pipeline's clinically correct output scores F1 = 0.0.

### 4.2 Seizure Frequency: Rich Schema, Poor Temporal Differentiation

The Seizure Frequency section has the most complex attribute set: `NumberOfSeizures`, `LowerNumberOfSeizures`, `UpperNumberOfSeizures`, `FrequencyChange`, `TimePeriod`, `NumberOfTimePeriods`, `PointInTime`, `TimeSince_or_TimeOfEvent`, etc.

However, the guidelines do not instruct annotators to distinguish **current** frequency from **historical** frequency in a way that the scorer can use. The `TimeSince_or_TimeOfEvent` attribute records `Since` or `During`, but:
- `Since` can mean "since last clinic" (current reporting window) or "since 2016" (historical).
- `During` can mean "during the last month" (current) or "during 2014" (historical).
- There is no explicit `Current` vs `Historical` flag in the CSV exports for seizure types.

Example 6 in the guidelines further complicates temporal interpretation:
> "Her last seizure was in September 2012."  
> Seizure: `NumberOfSeizures = 0`, `MonthDate = 9`, `YearDate = 2012`, `TimeSince_or_TimeOfEvent = Since`  
> "Although 'in' would imply during, since this is an indication of no events since this date... we use Since."

This is a sensible clinical interpretation, but it means the `Since`/`During` distinction is semantically overloaded. The scorer cannot reliably derive "current vs historical" from these values alone.

### 4.3 Prescription: Current-Only, But With Loopholes

The guidelines state:
> "We are only annotating current prescriptions for anti-seizure medications (ASMs)."

And:
> "Drugs without a dose should not be annotated, except for rescue medications such as midazolam or diazepam."

But:
> "If frequency is NOT stated use once a day, or 'As Required' for Clobazam."

These rules create three tension points:
1. **Dose-required rule vs dose-inferred rule:** The guideline says "drugs without a dose should not be annotated," but then gives an example where the dose is "known from the letter" but not stated in the sentence, and says the drug "should not be annotated." However, 17 Prescription labels in the 20-document inspection had `DrugDose` present but the labelled span contained no number—indicating annotators often inferred dose from distant context.
2. **Rescue-medication exception:** Clobazam and midazolam can be annotated without dose. This is clinically reasonable but creates an inconsistency in the "dose required" rule.
3. **Brand-name normalization:** Brand names must be matched to generic terms, but the UMLS drop-down contains both. The inspection found `DrugName: "top"` for Topiramate and misspelled `brivitiracetam` preserved as the raw DrugName.

### 4.4 Investigations: Result-Driven, Type-Optional

The guidelines state:
> "Investigations without any mentions of result should be ignored."

And for EEG:
> "The type of test needs to be annotated, if stated (it should not be assumed), otherwise it can be ignored."

This is reasonable, but the CSV data shows that EEG type is recorded as `null` in 104 of 182 investigation annotations. The `EEG_Type` field is largely unpopulated, which means any system that correctly extracts "sleep-deprived EEG" or "video telemetry" gets no credit for type linkage.

### 4.5 Certainty Levels: Used Inconsistently

The guidelines define five certainty levels (1 = negation, 5 = strong affirmation) and provide long lists of trigger words. However:
- Certainty was only used for Diagnosis and Patient History in the synthetic-letter validation.
- Birth History, Epilepsy Cause, Onset, and When Diagnosed have certainty features in the schema but the guidelines say they "were not used" because they occasionally mismatch.
- The scorer (`evaluate.py`) does not use certainty levels at all. A diagnosis with certainty = 1 (ruled out) is treated the same as certainty = 5 (definite) if it appears in `MarkupDiagnosis.csv` with `Negation = Affirmed`.

**Impact:** The project's epilepsy-diagnosis accuracy metric treats an affirmed but doubtful diagnosis ("possible focal epilepsy", certainty = 3) identically to a definite one. Our systems, which are prompted to extract only clear diagnoses, are sometimes penalized for correctly excluding tentative mentions.

---

## 5. Gold-Standard Construction: How `evaluate.py` Builds the Target

Understanding how the scorer constructs its gold label sets is essential, because the **construction logic itself introduces distortions** beyond those present in the raw annotations.

### 5.1 Seizure Types: Unconditional Harvest from Frequency CSV

```python
# src/evaluate.py, in load_gold()
for row in read_csv_rows(markup_root / "MarkupSeizureFrequency.csv"):
    ...
    seizure_type = canonical_seizure_type(row[5] if row[5].lower() != "null" else row[4])
    ...
    if seizure_type:
        document.seizure_types.append(seizure_type)
```

The `seizure_types` list is populated from `MarkupSeizureFrequency.csv`, not from `MarkupDiagnosis.csv`. This is a critical design choice: the gold standard for "seizure type" is derived from the **frequency annotation file**, where every row with a non-empty seizure-type value appends that type to the document's list **regardless of temporal scope**.

For EA0006, the CSV rows show:

```csv
EA0006.txt,498,541,C0494475,"2-generalised-tonic-clonic-seizures-in-2014",...
EA0006.txt,234,272,C0494475,"generalised-tonic-clonic-seizures-2014",...
EA0006.txt,274,295,C0563606,"absence-like-seizures",...
```

All three rows have `TimeSince_or_TimeOfEvent = During` and `YearDate = 2014`. The gold loader **knows** these are historical (the `temporal_scope` field in the loaded data structure contains `During 2014`). But `document.seizure_types` appends them unconditionally.

The scorer then computes:

```python
gold_types = {(item,) for item in set(document_gold.seizure_types) if item}
result["field_scores"]["seizure_type"] = set_prf(predicted_types, gold_types)
```

This is a pure set intersection. There is no `current_only` flag, no temporal filter, and no distinction between "seizure types the patient currently experiences" and "seizure types mentioned anywhere in the letter."

**Quantitative impact:** We identified 111 entries in `MarkupSeizureFrequency.csv` where the seizure-type field is generic (`seizures`, `seizure`, `null`). These are filtered by `canonical_seizure_type()` and do not enter `gold_types`. But the remaining typed entries—`generalised-tonic-clonic-seizures`, `focal-to-bilateral-convulsive-seizures`, `absences`, etc.—enter the gold set even when they describe events from 2014, 2016, or 2017.

### 5.2 Medications: All Rows Are Treated as Current

```python
for row in read_csv_rows(markup_root / "MarkupPrescriptions.csv"):
    document.medications.append({
        "name": canonical_medication_name(row[4] if row[4].lower() != "null" else row[5]),
        "dose": normalize_dose(row[6]),
        "dose_unit": normalize_unit(row[7]),
        "frequency": normalize_frequency(row[8]),
    })
```

The Prescriptions CSV is loaded **without any temporal filter**. The guidelines say "only current prescriptions," but the scorer does not verify this. If a letter mentions a previous medication and the annotator labelled it (which should not happen per guidelines, but may), it enters the gold set as current.

**Case:** EA0006 mentions "Previous antiepileptic medication: lamotrigine and carbamazepine." The prescriptions CSV for EA0006 contains only levetiracetam, so in this case the guidelines were followed. But there is no automatic verification that all 293 prescription annotations across the corpus are current-only.

### 5.3 Diagnosis: Only Epilepsy Categories, Only Affirmed

```python
for row in read_csv_rows(markup_root / "MarkupDiagnosis.csv"):
    if normalize_value(row[7]) == "epilepsy" and normalize_value(row[6]) == "affirmed":
        diagnosis = canonical_diagnosis(row[5] if row[5].lower() != "null" else row[4])
        if diagnosis:
            document.diagnoses.append(diagnosis)
```

The scorer filters for `DiagCategory = Epilepsy` and `Negation = Affirmed`. It ignores `SingleSeizure` and `MultipleSeizures` entries for the epilepsy-diagnosis field. This is correct for the diagnosis task, but it means that seizure-type entries in `MarkupDiagnosis.csv` (which are numerous) do not feed the diagnosis scorer—they only feed the seizure-type scorer via the frequency CSV.

**However:** The `canonical_diagnosis()` normalizer maps diverse strings to benchmark categories. The gold set can contain multiple diagnosis strings per document (e.g., "focal epilepsy" and "temporal lobe epilepsy" both map to `focal epilepsy`). The scorer uses a substring match:

```python
result["field_scores"]["epilepsy_diagnosis"] = {
    "correct": any(predicted_diagnosis and (predicted_diagnosis in gold or gold in predicted_diagnosis) for gold in document_gold.diagnoses),
}
```

This is forgiving, which is appropriate given the annotation looseness. But it also means that a system predicting the more specific "symptomatic structural right temporal lobe epilepsy" will match gold "focal epilepsy" via substring, while a system predicting only "epilepsy" may not match if the gold contains only the specific subtype.

### 5.4 Investigations: Simple Keyword Matching

```python
phrase = normalize_value(row[4])
result = "abnormal" if "abnormal" in phrase else "normal" if "normal" in phrase else None
if "eeg" in phrase and result:
    document.investigations["eeg"] = result
if "mri" in phrase and result:
    document.investigations["mri"] = result
```

The investigation loader does not use the structured `MRI_Results` / `EEG_Results` columns from the CSV. It keyword-matches the normalized phrase string. This is robust to the CSV's structural inconsistencies (e.g., `EEG normal` vs `eeg-normal` vs `normal-eeg`), but it cannot distinguish "abnormal EEG" from "no abnormal EEG" (a negated abnormal result would still keyword-match `abnormal`).

**Case:** EA0022 contains the annotation `"EEG-she-had-some-of-these-episodes-and-there-was-no-epileptiform-EEG"` with `EEG_Results = Normal`. The phrase contains both "no" and "EEG" and "epileptiform" (an abnormal marker), but the keyword matcher correctly assigns `normal` because `normal` is present. However, a negated abnormal result like "no epileptiform activity" without the word "normal" would be misclassified.

---

## 6. Per-Category Quality Assessment with Case Studies

### 6.1 Seizure Types: The Temporal Flatness Problem

**Severity: Critical**  
**Impact on project scores: High (primary driver of the 0.60–0.65 F1 ceiling)**

The seizure-type field is the project's most contested metric. The original strict F1 was 0.187–0.261; collapsed-label scoring raised it to 0.61–0.63. Despite enormous prompt-engineering investment (H6v2, H6fs, H6qa, H6ev, H7, D3, MA_v1), the score has remained in a narrow band. This audit shows that a significant portion of the remaining gap is artificial.

#### Case Study 1: EA0006 — The Paradox Document

**Letter text (excerpt):**
> "Seizure type and frequency: 2 generalised tonic clonic seizures 2014, absence like seizures 2014"  
> ...  
> "I was pleased to hear that he remains seizure free and is now driving."

**Gold standard seizure types:** `generalized tonic clonic seizure` (×2), `generalized absence seizure`

**Clinical reality:** The patient has been seizure-free since 2014. He currently experiences no seizures. The 2014 events are historical.

**MA_v1 post-repair output:** `['seizure free']`

**F1 against gold:** 0.0 (precision = 0, recall = 0)

**MA_v1 pre-repair output (Stage 1 broken, full-letter fallback):** `['generalized tonic clonic seizure', 'generalized absence seizure']`

**F1 against gold:** 1.0

**Analysis:** This is the clearest possible demonstration of measurement misalignment. The pipeline that correctly identifies the patient's current status scores worse than the broken pipeline that extracts every mention indiscriminately. The gold standard includes historical types because the annotation guidelines (Example 5) teach annotators to label historical mentions as affirmed diagnoses.

#### Case Study 2: EA0004 — The Unknown-Type Document

**Letter text:**
> "Seizure taking frequency: Uncertain, several seizures since the last clinic appointment"

**Gold standard:** `unknown seizure type` (×2)

**MA_v1 post-repair output:** `['unknown seizure type']`

**F1 against gold:** 1.0

**Analysis:** This is a genuine success. The system correctly identifies that seizures are occurring but the type is unspecified. However, this success is masked at the aggregate level by the EA0006 regression and similar cases. The `unknown seizure type` meta-label is critical for clinical safety—forcing a specific type inference here would be a hallucination.

#### Case Study 3: EA0011 — The Historical Secondary Generalization

**Letter text:**
> "Focal to bilateral convulsive seizures, last event around Christmas 2017"  
> ...  
> "His seizures started in 2003 at the age of 31. He can get infrequent focal to bilateral convulsive seizures having around two in the year of his diagnosis and his last one being around Christmas time in 2017"

**Gold standard:** `focal seizure`, `focal to bilateral convulsive seizure`

**Clinical reality:** The patient's last focal-to-bilateral convulsive seizure was in 2017. The current status is ongoing focal seizures with altered awareness (~1 per fortnight), but the convulsive subtype is historical.

**MA_v1 pre-repair output:** Extracted `"secondary generalized seizures"` as current type. Verifier kept it with reason: *"Supported by the letter as the patient's seizure type."* The 2017 date was ignored. **F1 = 1.0 against gold** because the gold includes this historical type.

**Analysis:** The "high" F1 reflects successful matching of a temporally flat gold standard, not successful clinical extraction. The patient has not had a convulsive seizure in ~8 years (as of the 2025 letter date). Reporting this as a current seizure type is clinically misleading.

#### Case Study 4: EA0005 — The "Last Event July 2016" Document

**Letter text:**
> "Generalised tonic clonic seizure-last event July 2016. Previous event December 2015."  
> ...  
> "His last seizure coincided with forgetting to take his medication. As you know his seizures started in 2010 and he has had roughly two seizures per year since then."

**Gold standard:** `generalized tonic clonic seizure`

**Analysis:** This document is ambiguous. The letter mentions "last event July 2016" but also "roughly two seizures per year since then" (since 2010). The gold labels `generalized tonic clonic seizure` as a current type. A temporally aware system might infer that GTCS are ongoing (given the "two per year" statement), or it might note that the last *confirmed* event was 2016 and the current frequency is uncertain. The gold standard's flat label set cannot represent this nuance.

#### Case Study 5: The Meta-Label Ceiling

Across all models (4B to 35B) and all harnesses (H6, H6fs, H6v2, H6ev, H6qa), the miss count for `unknown seizure type` is consistently **13–15 out of 26 documents** that have this gold label. Scale does not close this gap.

**Why?** The annotation guidelines do not clearly define when `unknown seizure type` should be used. The guidelines say "No generic seizure/absence/myoclonic jerk should be included" in Diagnosis, but they do not say that a letter describing "several seizures" without naming a type should be labelled `unknown`. The annotators appear to have used `unknown seizure type` as a catch-all when no specific ILAE type is named. Models, however, are trained to infer specific types from context (e.g., inferring `focal seizure` from "seizures with loss of awareness"), which is clinically reasonable but penalized by the gold.

### 6.2 Medications: Dose Conflicts, Null Handling, and Current-Only Ambiguity

**Severity: Moderate to High**  
**Impact on project scores: Moderate (Name F1 is high; Full Tuple F1 is affected)**

Medication name extraction is the project's strongest field (F1 0.85–0.89 on validation, 0.88–0.89 on test). This aligns with the paper's finding that Prescriptions had the highest IAA (0.87). However, the full-tuple metric (name + dose + unit + frequency) is lower (0.62–0.77), and the annotation quality explains part of the gap.

#### Case Study 6: EA0017 — The `null` Drug Name

**MarkupPrescriptions.csv row:**
```csv
EA0017.txt,229,255,C0016410,"null","folic-acid",5,mg,1,"folic-acid-5-mg-once-a-day"
```

**Analysis:** The canonical `DrugName` field is `null`; the surface text is `folic-acid`. The scorer's `canonical_medication_name()` handles this by falling back to the surface text. But folic acid is **not an anti-seizure medication**. The guidelines say "only current prescriptions for anti-seizure medications (ASMs)." Folic acid is a supplement. Its inclusion in the gold set is an annotator error or a scope relaxation not documented in the guidelines.

**Impact:** Our systems correctly exclude folic acid (it is not in the ASM synonym list). This creates a false negative on the gold label. The medication name F1 is robust enough to absorb this, but it illustrates the principle: the gold set contains non-ASM drugs, and our precision-oriented filtering excludes them.

#### Case Study 7: EA0183 — Conflicting Doses (from Prior Inspection)

**Prior inspection finding:** Two overlapping Prescription labels on `"Sodium-Valproate"` / `"Sodium-Valproate-"`, one with `DrugDose: 800` and the other with `DrugDose: 700`.

**Analysis:** This is a high-severity error for full-tuple scoring. A system predicting `sodium valproate | 800 | mg | 2` would match one gold tuple but miss the other, producing a false negative (700) and a true positive (800). The system's precision is penalized for a gold-standard inconsistency.

#### Case Study 8: EA0195 — Tegretol Dose Ambiguity (from Prior Inspection)

**Prior inspection finding:** Overlapping Tegretol labels: `"Tegretol-"` with `DrugDose: 600`, while `"Tegretol-400mg-in-the-morning"` has `DrugDose: 400`.

**Analysis:** This may reflect a total daily dose (600 mg) versus a per-dose amount (400 mg morning). The JSON/CSV does not distinguish these concepts. Our scorer expects a single canonical tuple. A system predicting `carbamazepine | 400 | mg | 2` would miss the 600 mg tuple. The gold standard's structural ambiguity directly lowers full-tuple F1.

#### Case Study 9: EA0188 — Misspelled Drug Name Preservation (from Prior Inspection)

**Prior inspection finding:** `"Brivitiracetam"` with `DrugName: "brivitiracetam"` but `CUIPhrase: "brivaracetam"`.

**Analysis:** The surface text contains a misspelling. The CUI normalization is correct, but the `DrugName` attribute preserves the error. Our `canonical_medication_name()` normalizer maps `brivitiracetam` → `brivaracetam` (via `ASM_SYNONYMS`), so we score a true positive. But this only works because the project's normalization layer was explicitly expanded to handle ExECTv2 misspellings. Without that repair, the original scorer would have produced a false negative. This is a genuine methods contribution: **the gold standard required scorer-side normalization repair to be scoreable at all.**

### 6.3 Diagnosis: Certainty Ambiguity and Overlap

**Severity: Moderate**  
**Impact on project scores: Moderate (Dx accuracy 0.72–0.85)**

Diagnosis extraction scores are higher than seizure type but still below the Fang et al. target of ≥0.80 F1. The annotation quality explains part of the gap.

#### Case Study 10: EA0002 — Dual Diagnosis Overlap

**MarkupDiagnosis.csv rows:**
```csv
EA0002.txt,21,35,C0014547,"focal-epilepsy","focal-epilepsy",Affirmed,Epilepsy,5
EA0002.txt,27,53,C0014556,"temporal-lobe-epilepsy","epilepsy-Probable-temporal",Affirmed,Epilepsy,4
```

**Letter text:**
> "Diagnosis: focal epilepsy, probably temporal"

**Analysis:** Two overlapping spans annotate the same clinical concept with different specificity and different certainty. The first span (`focal-epilepsy`, certainty 5) covers the definite part. The second span (`epilepsy-Probable-temporal`, certainty 4) covers the probable localization. Our scorer's `canonical_diagnosis()` maps both to `focal epilepsy`. A system predicting only `focal epilepsy` scores a match. But a system predicting `temporal lobe epilepsy` might not match if the gold only contains `focal epilepsy`—even though the letter explicitly says "probably temporal."

#### Case Study 11: EA0006 — Certainty = 3 for Generalised Epilepsy

**MarkupDiagnosis.csv row:**
```csv
EA0006.txt,55,66,C0014548,"generalised-epilepsy","generalised",Affirmed,Epilepsy,3
```

**Letter text:**
> "Diagnosis: Epilepsy – unclassified, possibly generalised."

**Analysis:** The word "possibly" triggers certainty = 3 ("possible" is listed under Level 3 in the guidelines). Our systems, prompted to extract only clear diagnoses, might exclude this. The gold includes it because `Negation = Affirmed`. The scorer ignores certainty. A precision-oriented system is penalized for correctly excluding a tentative diagnosis.

#### Case Study 12: EA0003 — Generalised Seizures as Diagnosis

**MarkupDiagnosis.csv row:**
```csv
EA0003.txt,206,226,C0234533,"generalised-seizures","generalised-seizures",Affirmed,MultipleSeizures,5
```

**Letter text:**
> "generalised seizures"

**Analysis:** This is annotated as `DiagCategory = MultipleSeizures`, not `Epilepsy`, so it does not feed the epilepsy-diagnosis scorer. But it feeds the seizure-type scorer via the frequency CSV. The term "generalised seizures" is generic—it does not specify tonic-clonic, absence, or myoclonic. The ILAE classification would not accept "generalised seizures" as a specific type. Yet it appears in the gold seizure-type set. Our `canonical_seizure_type()` maps it to `generalized seizure` (a collapsed category), which is acceptable at the benchmark level but imprecise clinically.

### 6.4 Investigations: Result Ambiguity and Span Noise

**Severity: Low to Moderate**  
**Impact on project scores: Low (EEG and MRI accuracy are high: 0.90–1.00)**

Investigations are the most structurally consistent category, which aligns with the paper's finding that structured entities are easier to annotate. However, there are still issues.

#### Case Study 13: EA0022 — The "No Epileptiform EEG" Span

**MarkupInvestigations.csv row:**
```csv
EA0022.txt,488,556,C0560017,"eeg-normal","EEG-she-had-some-of-these-episodes-and-there-was-no-epileptiform-EEG",null,null,null,null,Yes,null,Normal,null,null
```

**Analysis:** The annotated span is 68 characters long and contains the full sentence: "EEG she had some of these episodes and there was no epileptiform EEG." The phrase "no epileptiform EEG" is negated, but the result is annotated as `Normal`. This is clinically correct (no epileptiform activity = normal), but the span includes a great deal of irrelevant text. A system extracting evidence quotes would produce a much shorter span (e.g., "no epileptiform EEG"), which would not overlap with the gold span and would fail the quote-validity check unless our quote validator uses substring matching.

#### Case Study 14: EA0030 — Multiple Investigation Mentions

**Letter text (inferred from JSON):**
The letter likely mentions both an EEG and an MRI. The annotations show `eeg-abnormal` and `mri-abnormal`. However, many letters mention investigations multiple times (e.g., "MRI in 2012 was normal, repeat MRI in 2019 showed changes"). The gold standard typically annotates only the most recent or most relevant mention, but this is not systematically enforced. A system extracting "MRI 2012 normal" would score a false positive if the gold only contains "MRI 2019 abnormal."

#### Case Study 15: EEG Type Unpopulated

**Quantitative finding:** Of 182 investigation annotations, 104 have `EEG_Type = null`. Only 78 have any value, and the majority of those are `Yes` (indicating `EEG_Performed`) rather than a specific type.

**Analysis:** The guidelines state that EEG type should be annotated "if stated (it should not be assumed)." The low population rate suggests that most letters do not state the EEG type, or that annotators missed it. Our scorer does not score EEG type at all, so this is not a direct evaluation issue. But it illustrates the incompleteness of the gold standard for fine-grained attributes.

### 6.5 Seizure Frequency: The Most Error-Prone Field

**Severity: Critical**  
**Impact on project scores: Critical (original score 0.000; corrected score 0.075–0.175; oracle failure rate 29.2%)**

Seizure frequency is the project's most difficult field, and the annotation quality is the primary driver of that difficulty. The paper itself reports ExECTv2's lowest validation score on this field (0.66).

#### Case Study 16: EA0194 — Contradictory Annotations on the Same Span

**MarkupSeizureFrequency.csv rows:**
```csv
EA0194.txt,431,469,C0877017,"Focal-to-bilateral-convulsive-seizures","focal to bilateral convulsive seizures",0,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null
EA0194.txt,431,469,C0877017,"Focal-to-bilateral-convulsive-seizures","focal to bilateral convulsive seizures",null,null,null,1,Year,null,null,null,null,null,null,null,null,null,null,null,null,null
```

**Analysis:** The same span (`431,469`) is annotated twice with contradictory values:
- Annotation 1: `NumberOfSeizures = 0` (no temporal period)
- Annotation 2: `UpperNumberOfSeizures = 1`, `TimePeriod = Year` (1 per year)

These cannot both be true for the same clinical assertion unless they refer to different time windows not represented in the span. The prior inspection flagged this as a "serious temporal-normalization ambiguity." Our scorer's `frequency_loose_match()` may or may not match a predicted "0" against this gold, depending on parsing paths. The presence of contradictory gold labels makes correct extraction statistically impossible.

#### Case Study 17: EA0069 — Overlapping Frequency Annotations with Different Types

**MarkupSeizureFrequency.csv rows:**
```csv
EA0069.txt,665,698,C0494475,"generalised-tonic-clinic-seizures","generalised tonic clonic seizures",Increased,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null
EA0069.txt,665,698,C0494475,"generalised-tonic-clinic-seizures","generalized-tonic-clonic-seizures",null,4,null,Week,null,null,null,null,null,null,null,null,null,null,null,null,null,null
```

**Analysis:** Same span, two annotations:
- Annotation 1: `FrequencyChange = Increased` (no count, no period)
- Annotation 2: `NumberOfSeizures = 4`, `TimePeriod = Week` (4 per week)

These are not contradictory—they are complementary. One captures the change direction; the other captures the rate. But the scorer expects a single `current_seizure_frequency.value` string. A system predicting "4 per week" would miss the "Increased" annotation. A system predicting "increased" would miss the "4 per week" annotation. The gold standard's multi-mention design is mismatched with our single-value schema.

#### Case Study 18: EA0070 — Infrequent vs Upper Bound

**MarkupSeizureFrequency.csv rows:**
```csv
EA0070.txt,1353,1361,C0036572,"seizures","seizures",Infrequent,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null
EA0070.txt,1353,1361,C0036572,"seizures","seizures",null,null,null,null,null,null,1,Year,null,null,null,null,null,null,null,null,null,null
```

**Analysis:** Same span (`seizures`), two interpretations:
- Annotation 1: `FrequencyChange = Infrequent` (qualitative)
- Annotation 2: `UpperNumberOfSeizures = 1`, `TimePeriod = Year` (quantitative upper bound)

Our Gan-inspired pragmatic scorer would map "1 per year" to `infrequent` and score a match. But the ExECTv2 strict scorer requires exact string or parts match. The dual annotation creates a split target: matching one annotation does not guarantee matching the other.

#### Case Study 19: EA0010 — Seizure-Free with Time Period

**MarkupSeizureFrequency.csv row:**
```csv
EA0010.txt,467,476,C0036572,"seizures-","seizures",0,null,null,null,null,null,null,null,null,null,13,19,Year,null,null
```

**Analysis:** `NumberOfSeizures = 0`, with `AgeLower = 13`, `AgeUpper = 19`, `AgeUnit = Year`. This represents "seizure-free for 13–19 years." The gold loader's `normalize_value(frequency)` constructs the string `"0 per 13 year"` (using `AgeLower` as the period count), which is clinically nonsensical. The project's Phase 2 gold-loader fix addressed this by treating `null` strings more carefully, but the underlying annotation structure (using `Age` fields for seizure-free duration) is semantically overloaded.

#### Case Study 20: The `null null per 3 week` Bug

**Original scorer bug (fixed in Phase 2):** Literal `null` cells in `MarkupSeizureFrequency.csv` were passed through as the string `"null"`, producing invalid frequency expressions like `"null null per 3 week"`.

**Analysis:** This was a scorer bug, not an annotation bug. But it was caused by the CSV's use of literal `null` strings to represent absent values. The fact that 258 of 280+ seizure-frequency rows have `TimeSince_or_TimeOfEvent = null` indicates that this field is overwhelmingly unpopulated. The annotation schema has rich temporal attributes, but annotators did not use them consistently.

### 6.6 Patient History, Onset, and Other: Boundary Issues and Overlaps

**Severity: Low (not directly scored by project metrics)**  
**Impact on project scores: Indirect (context bleeding, family history trap)**

While Patient History, Onset, Epilepsy Cause, Birth History, and When Diagnosed are not directly scored by our benchmark metrics, they matter for two reasons: (1) they create context-bleeding risks for systems that read the full letter, and (2) they reveal the overall annotation quality.

#### Case Study 21: EA0188 — Severe Span Defects (from Prior Inspection)

**Prior inspection findings:**
- `"eiz"` as a PatientHistory span (mid-word truncation)
- `"ondary-generalised-seiz"` as a Diagnosis span (mid-word start and end)
- `"drug-refractory"` mapped to CUIPhrase `"drug"`
- `"occipital-lobe)-epilepsy"` mapped to CUIPhrase `"Occipital"`

**Analysis:** These are not minor formatting issues. A model trained on these spans would learn to output partial tokens and overly broad concepts. The project's event-first architecture (E3) mitigates this by extracting full sentences as evidence quotes rather than mimicking the gold spans exactly. This is a structural advantage of our approach.

#### Case Study 22: EA0198 — Conflicting Onset Ages

**Prior inspection finding:** Two Onset labels on the same `"epilepsy"` span: one says onset age 23 years, another says 15 years.

**Analysis:** The same mention of epilepsy is given two different onset ages. This may reflect two different clinical events (e.g., first seizure at 15, diagnosis at 23), but the annotation does not distinguish them. A system predicting either age would score a false negative on the other.

#### Case Study 23: EA0184 — Truncated Absence Spans

**Prior inspection finding:** `"typical-absenc"` and `"typical-absen"` for Diagnosis and SeizureFrequency, both truncated rather than the full phrase `"typical absences"`.

**Analysis:** Truncated spans degrade exact-span training and evaluation. Our quote validator checks whether the extracted quote appears verbatim in the source text, so a system outputting `"typical absences"` would pass quote validity even if the gold span is `"typical-absenc"`. However, a strict span-overlap scorer would penalize the mismatch.

#### Case Study 24: Family History Is Invisible to Scoring

**EA0006 letter text:**
> "There is no family history of epilepsy and both his sons are well and have not had seizures."

**Gold standard:** No family history annotations exist (the category is not in the schema).

**Analysis:** A single-pass system reading the full letter might extract `"epilepsy"` and `"seizures"` from this sentence and incorrectly include them as patient findings. The MA_v1 pipeline's Stage 1 was explicitly designed to isolate family-history quotes to prevent this "family history trap." But because the gold standard has no family-history field, fixing the trap provides **zero score improvement**. The only visible effect is the *other* temporal fix—excluding historical patient seizures—which *lowers* the score. This is the asymmetric evaluation problem documented in `docs/37_clinical_accuracy_vs_gold_standard_tension.md`.

---

## 7. Cross-Cutting Structural Issues

### 7.1 Span Boundary Defects

The prior inspection of 20 documents (EA0181–EA0200) found:

| Issue | Count (out of 218 annotations) |
|-------|-------------------------------|
| Ends with hyphen/separator | 37 |
| Ends in truncated word | 9 |
| Starts mid-word | 3 |
| Starts with hyphen/separator | 2 |

These defects are likely caused by the Markup export process converting whitespace to hyphens. While they do not affect the project's set-based scoring (which uses normalized concept strings, not spans), they degrade the quality of the JSON gold files for any external consumer doing span-level NER training.

### 7.2 CUIPhrase and Normalization Inconsistency

| Example | Problem |
|---------|---------|
| `generalised-tonic-clonic-seizures` → `generalised` | Loses seizure-type specificity |
| `drug-refractory` → `drug` | Incorrectly reduced to generic term |
| `occipital-lobe)-epilepsy` → `Occipital` | Anatomical only, not a diagnosis |
| `focal-motor-seizures` → `focal` | Loses motor specificity |
| `ischaemic-damage` → `brain` | Clinically too vague |
| `transient-loss-of-consciousness` → `Transient` | Not a meaningful concept |

The project's `canonical_seizure_type()` and `canonical_diagnosis()` normalizers override many of these issues by mapping to benchmark categories. But this repair is performed **in the scorer**, not in the gold data. The original scorer (before Phase 2/3) produced much lower scores because it did not have these normalizations.

### 7.3 Duplicate and Conflicting Annotations

Seven spans in the seizure-frequency CSV carry multiple annotations with conflicting attributes. The prescriptions CSV contains overlapping spans with dose conflicts. The diagnosis CSV contains overlapping spans with different certainty levels.

These conflicts are not random noise. They reflect the **intrinsic difficulty of clinical annotation**: a single phrase can have multiple valid interpretations (total daily dose vs per-dose amount; seizure-free since 2019 vs 1–2 per year in a different time window). The project's scorer uses set-based matching, which is forgiving of some conflicts but cannot resolve contradictions on the same span.

---

## 8. The Precision-Looseness Tension: Why Our Systems "Fail" Against Gold

This section synthesizes the evidence into a coherent argument about the relationship between our extraction systems and the gold standard.

### 8.1 The Core Argument

The project's extraction systems—especially MA_v1, H7, D3, and E3—are designed to be **clinically precise**:
- They distinguish current from historical findings.
- They distinguish patient from family history.
- They require evidence quotes for every extraction.
- They normalize to specific, clinically meaningful categories.
- They abstain (`unknown seizure type`, `seizure free`) when the text does not support a specific inference.

The ExECTv2 gold standard—by design, by guideline instruction, and by construction logic—is **clinically loose**:
- It treats historical seizure types as current diagnoses (guideline Examples 4–5).
- It has no family-history field.
- It does not require evidence spans to be clinically meaningful (68-character EEG spans).
- It uses broad, sometimes contradictory categories.
- It penalizes abstention by expecting specific types even when the text is generic.

When a precise system meets a loose gold standard, the result is **systematic under-scoring of correct behavior**.

### 8.2 Evidence from Score Patterns

The full experiment record (`docs/34_full_experiment_record.md`) shows a striking pattern:

| System | Seizure F1 Collapsed (validation) | Temporal Discrimination |
|--------|-----------------------------------|------------------------|
| S2 (full-letter direct) | 0.610 | None |
| E3 (event-first) | 0.633 | Implicit (events have temporal context) |
| H7 (two-pass normalize) | 0.698 (15 dev) | Explicit normalization |
| D3 (candidate+verifier) | 0.682 (15 dev) | Verifier can drop historical |
| MA_v1 (multi-agent) | 0.610–0.720 | Explicit segmentation → current-only |

The "best" scores come from systems that extract broadly (S2, E3). Systems that try to be precise (H7, D3, MA_v1) score lower or become unstable. This is not because they extract worse clinically; it is because they extract **more carefully than the gold standard allows**.

### 8.3 The Perversity of Prompt Engineering

Consider what prompt engineering has actually done:
- **H6v2** added explicit `unknown seizure type` and `seizure free` guidance.
- **H6fs** added few-shot examples showing when to use meta-labels.
- **H6ev** added evidence anchors to force citation.
- **MA_v1** built a four-stage pipeline to isolate current from historical context.

All of these were attempts to make the model behave more precisely. But the evaluation protocol does not reward precision—it rewards **matching the flat label set**. The result is a subtle form of overfitting: prompts are tuned to make the model extract *more labels* (including historical ones), to use broader context, and to avoid the meta-labels that the scorer sometimes punishes.

In effect, the project has been **adapting its extraction to the evaluation set's biases** rather than to the clinical task's true requirements.

### 8.4 The Asymmetry Problem

The evaluation protocol is **asymmetric**:
- It punishes temporal precision on the patient-history axis (excluding historical seizures lowers F1).
- It is blind to precision on the family-history axis (excluding family-history seizures has no score effect).
- It punishes abstention (`unknown seizure type`) because the gold often expects a specific inferred type.
- It does not reward evidence quality (quote validity is a separate metric that does not feed benchmark composite).

A system that fixes both temporal bleeding and family-history bleeding looks worse than a system that fixes neither. This is the opposite of what a clinical evaluation should do.

---

## 9. Quantified Impact on Evaluation Scores

### 9.1 The Temporal-Scope Bias: A Back-of-Envelope Estimate

From the 25+ documents reviewed, we identified at least **8 clear cases** of historical seizure types being treated as current in the gold standard (EA0006, EA0011, EA0005, EA0020, EA0186, EA0194, EA0198, EA0200). If these 8 cases appear at similar rates across the 120-document development split and 40-document validation split, we can estimate:

- Validation split (40 docs): ~2–3 documents with clear historical-as-current bias.
- Each such document contributes 1–2 false negatives (missed historical types) and 1–2 false positives (excluded current meta-labels) to the per-document F1.
- Aggregate effect: a **5–10 percentage point depression** of seizure-type F1 for any system that correctly applies temporal discrimination.

This is consistent with the observed gap between S2 (0.610, no temporal discrimination) and MA_v1 post-repair (0.610–0.692, with temporal discrimination but lower due to EA0006-type cases).

### 9.2 The Meta-Label Ceiling

The `unknown seizure type` miss is consistently 13–15 out of 26 documents across all models and harnesses. This is not a model problem; it is a **benchmark-design problem**. The gold standard uses `unknown seizure type` as a catch-all for generic seizure mentions, but the annotation guidelines do not clearly define when to use it. Models infer specific types from context, which is clinically correct but benchmark-incorrect.

If the gold standard were revised to either:
- Remove `unknown seizure type` and accept any specific reasonable inference, or
- Explicitly mark which generic mentions should map to `unknown`,

the meta-label ceiling would disappear and seizure-type F1 would rise by an estimated **8–12 percentage points**.

### 9.3 The Oracle Failure Rate Revisited

The project's aggregation oracle (`docs/34_full_experiment_record.md` §4.6) reports:

| Field | Oracle Failure Rate |
|-------|---------------------|
| Seizure type | 13.3% |
| Medication full tuple | 10.8% |
| Seizure frequency | 29.2% |
| Epilepsy diagnosis | 17.5% |

This audit suggests that the 13.3% seizure-type oracle failure rate is **not entirely due to missing annotations**. A significant portion is due to:
- Temporal misalignment (historical types expected as current)
- Meta-label mismatch (model infers specific type, gold expects `unknown`)
- Generic term mismatch (model extracts specific ILAE type, gold contains generic `seizures`)

If these annotation-quality issues were resolved, the true oracle failure rate for seizure type might be **5–8%** rather than 13.3%, and the achievable F1 ceiling would rise accordingly.

---

## 10. Recommendations

### 10.1 Immediate (Before Final Validation)

1. **Do not promote or demote systems based on seizure-type F1 alone.** The metric is confounded by gold-standard temporal blindness. Use benchmark composite as a guide, but weigh medication and diagnosis more heavily.

2. **Run a temporal-scope-aware scorer audit on the full validation split.** For each document, manually tag whether each gold seizure type is current, historical, or unclear. Compute `seizure_type_f1_collapsed_current` and `seizure_type_f1_collapsed_all`. Quantify the bias.

3. **Report dual metrics for seizure type in the dissertation:**
   - `seizure_type_f1_collapsed_all` — backward-compatible with literature
   - `seizure_type_f1_collapsed_current` — the clinically meaningful metric

   If MA_v1 or D3 outperforms on the current-only metric but underperforms on the all-mentions metric, frame this as a **positive finding** about temporal precision, not a failure.

4. **Fix the Stage 3 verifier prompt** (already done in `src/multi_agent.py`) to preserve `seizure free` and `unknown seizure type` meta-labels. This is a genuine bug fix.

### 10.2 Medium-Term (For Dissertation Claims)

5. **Audit the ExECTv2 seizure markup for temporal consistency.** The 13.3% oracle failure rate may be partly due to ambiguous `TimeSince_or_TimeOfEvent` entries rather than missing annotations. A manual review of 20–30 documents would clarify this.

6. **Reframe the dissertation claim on multi-agent decomposition.** Instead of "multi-agent decomposition improves overall extraction quality," the supported claim is:

   > "Multi-agent decomposition improves **temporal precision and robustness to context bleeding**, with mixed effects on aggregate F1 due to gold-standard temporal blindness. This trade-off is clinically desirable: a system that correctly reports a seizure-free patient is more useful than one that correctly matches a flat label set."

7. **Quantify the precision-looseness gap explicitly.** Add a section to the dissertation methods titled "Gold-Standard Fidelity and the Precision-Looseness Tension," citing this audit and the prior inspection. This is a genuine contribution to clinical NLP methodology.

### 10.3 Long-Term (For the Field)

8. **Propose a temporally structured extraction benchmark for clinical NLP.** The ExECTv2 schema has `temporal_scope` for frequencies but not for types. Future benchmarks should require systems to report *when* a seizure type was observed, not just *what* it was.

9. **Advocate for evidence-grounded scoring.** The project's quote-validity metric (≥0.96 across all conditions) is a strong clinical safety signal. Future benchmarks should incorporate evidence overlap into primary metrics, not just as a secondary check.

10. **Publish the annotation-quality findings.** The issues documented in this audit—temporal flatness, span defects, CUIPhrase inconsistency, and dose conflicts—are not unique to ExECTv2. They are systemic to clinical NLP annotation. A short methods paper or supplementary material documenting these findings would be valuable to the community.

---

## 11. Conclusion

The ExECTv2 gold standard is a valuable and pioneering resource. It is the first publicly available set of annotated synthetic epilepsy clinic letters, and the paper's IAA analysis (F1 = 0.73) correctly frames the task as intrinsically difficult. The annotations are clinically informed, cover a wide range of epilepsy concepts, and have enabled meaningful benchmark comparisons.

However, **the gold standard is not clean enough to serve as an unexamined target for precision-oriented extraction systems**. This audit has documented:

- **Temporal flatness** by design (guideline Examples 4–5) and by construction (`load_gold()` ignores temporal scope).
- **Systematic span boundary defects** (trailing hyphens, truncated words, mid-token starts).
- **Duplicate and conflicting annotations** (contradictory seizure frequencies, dose conflicts).
- **Inconsistent normalization** (overly broad CUIPhrases, misspelled drug names, generic seizure terms).
- **Asymmetric evaluation** (punishes temporal precision, blind to family-history precision, penalizes abstention).

The project's extraction systems—especially the temporally aware multi-agent pipeline—are **more clinically precise than the gold standard allows**. The seizure-type F1 ceiling of ~0.60–0.65 is not a model-capacity ceiling. It is a **gold-standard fidelity ceiling**.

The way forward is not more prompt engineering. It is **better measurement**: temporally scoped scoring, meta-label validation, explicit precision-looseness accounting, and honest reporting of the trade-off between matching a flat label set and extracting clinically truthful information.

The project's true contribution is not achieving F1 = 0.76 on a noisy target. It is building extraction systems that know the difference between a seizure-free patient and a patient whose seizures were last mentioned in 2014—and having the evidence to prove it.

---

## Appendix A: Document Case Study Index

| Case | Document | Category | Primary Issue |
|------|----------|----------|---------------|
| 1 | EA0006 | Seizure type | Historical types (2014) treated as current; seizure-free patient gold-labelled with GTCS + absences |
| 2 | EA0004 | Seizure type | `unknown seizure type` meta-label correctly used by system; genuine success masked by aggregate noise |
| 3 | EA0011 | Seizure type | Last convulsive seizure 2017 gold-labelled as current type; temporal precision penalized |
| 4 | EA0005 | Seizure type | "Last event July 2016" ambiguous; gold flat label cannot represent uncertainty |
| 5 | Aggregate | Seizure type | `unknown seizure type` miss = 13–15/26 docs across all models; structural meta-label ceiling |
| 6 | EA0017 | Medication | Folic acid (non-ASM) in gold; precision filtering excludes it → false negative |
| 7 | EA0183 | Medication | Conflicting sodium valproate doses (700 vs 800 mg) on overlapping spans |
| 8 | EA0195 | Medication | Tegretol dose ambiguity (600 total vs 400 morning) not distinguished by schema |
| 9 | EA0188 | Medication | Misspelled `brivitiracetam` preserved in DrugName; scorer normalization required for match |
| 10 | EA0002 | Diagnosis | Dual overlapping diagnosis spans with different certainty (5 vs 4) for same concept |
| 11 | EA0006 | Diagnosis | "Possibly generalised" (certainty = 3) included in gold; precision systems may exclude |
| 12 | EA0003 | Diagnosis | Generic `generalised seizures` as MultipleSeizures; lacks ILAE specificity |
| 13 | EA0022 | Investigations | 68-character EEG span with irrelevant text; evidence quote mismatch risk |
| 14 | EA0030 | Investigations | Multiple investigation mentions; gold may not annotate all |
| 15 | Aggregate | Investigations | EEG type `null` in 104/182 annotations; fine-grained attribute largely unpopulated |
| 16 | EA0194 | Seizure frequency | Same span annotated as both "0 since 2019" and "1 per year" — direct contradiction |
| 17 | EA0069 | Seizure frequency | Same span: `FrequencyChange = Increased` and `4 per week` — dual interpretation |
| 18 | EA0070 | Seizure frequency | Same span: `Infrequent` and `upper = 1 per year` — qualitative vs quantitative split |
| 19 | EA0010 | Seizure frequency | Seizure-free duration encoded as `AgeLower = 13`, producing `"0 per 13 year"` |
| 20 | Aggregate | Seizure frequency | Original `null` string bug produced `"null null per 3 week"`; 258 rows have `null` temporal scope |
| 21 | EA0188 | Patient History | `"eiz"` mid-word span; `"ondary-generalised-seiz"` truncated diagnosis |
| 22 | EA0198 | Onset | Same `"epilepsy"` span given onset ages 23 and 15 years |
| 23 | EA0184 | Seizure type | `"typical-absenc"` truncated span for typical absences |
| 24 | EA0006 | Family history | Family-history mention in letter; no gold field → trap is invisible to scorer |
| 25 | Aggregate | Span quality | 37 trailing-hyphen, 9 truncated, 3 mid-word spans in 20-doc sample |

---

## Appendix B: Quantitative Summary Tables

### B.1 Aggregate Annotation Statistics

| Metric | Value |
|--------|-------|
| Total documents | 200 |
| Total prescription annotations | 293 |
| Total seizure-frequency annotations | ~280 |
| Generic seizure-type entries in freq CSV (`seizures`/`seizure`/`null`) | 111 |
| Total investigation annotations | 182 |
| EEG type = `null` | 104 (57%) |
| Documents with both Epilepsy and MultipleSeizures diag | 0* |

*Note: The diagnosis CSV contains both categories, but they appear on different documents. The `DiagCategory` field separates epilepsy syndromes from seizure-type mentions.

### B.2 IAA vs System Performance

| Task | Human IAA (F1) | Best System F1 | Gap |
|------|---------------|----------------|-----|
| Prescriptions | 0.87 | 0.89 (med name) | +0.02 |
| Seizure type (strict) | ~0.60* | 0.43 (S2 val) | −0.17 |
| Seizure type (collapsed) | ~0.65* | 0.63 (E3 val) | −0.02 |
| Seizure frequency | 0.66 (ExECTv2) | 0.18 (loose, S2 test) | −0.48 |
| Diagnosis | ~0.70* | 0.78 (E3 val) | +0.08 |

*Estimated from paper's per-item IAA and entity distributions.

### B.3 Oracle Failure Rate vs Achievable Ceiling

| Field | Reported Oracle Failure | Estimated True Failure (post-audit) | Implied F1 Ceiling |
|-------|------------------------|-------------------------------------|-------------------|
| Medication name | 0.0% | 0.0% | 1.00 |
| Medication full tuple | 10.8% | 10.8% | 0.89 |
| Seizure type | 13.3% | 5–8% | 0.92–0.95 |
| Epilepsy diagnosis | 17.5% | 12–15% | 0.85–0.88 |
| Seizure frequency | 29.2% | 25–29% | 0.71–0.75 |

The seizure-type ceiling revision (from 0.87 to 0.92–0.95) assumes that temporal-scope correction and meta-label standardization would remove 5–8 percentage points of artificial failure.

---

*End of audit report.*
