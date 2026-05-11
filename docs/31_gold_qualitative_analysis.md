# Gold Label Qualitative Analysis

**Date:** 2026-05-10  
**Basis:** Direct reading of source letters, annotation files, JSON records, and analysis texts across both datasets. Independent of quantitative audit counts — those numbers are interrogated here for what they actually mean.

---

## Framing

The quantitative audit produced rates. This document asks what those rates represent. For each major finding, the question is: does this change the clinical meaning of the label, is it a metadata or tooling artefact, or is it a genuine epistemic error about what the letter says?

Three categories are distinguished throughout:

- **Tooling artefact** — correct annotation intent, incorrect or mismatched storage due to export pipeline or text preprocessing. Does not affect clinical meaning; does affect evaluation pipeline.
- **Schema limitation** — the annotation schema cannot represent a clinical reality cleanly, so annotators made a locally reasonable but globally ambiguous choice. The label is not wrong; the schema is under-powered.
- **Genuine labelling error** — the annotation makes a wrong clinical claim about the letter content, or assigns contradictory values to the same clinical fact.

---

## Part 1: ExECT 2 (2025)

### 1.1 The E1 span-boundary mismatches are almost entirely a text-preprocessing artefact

**Verdict: tooling artefact. Not an annotation quality problem.**

Reading the actual examples makes the root cause clear. The Gold1-200_corrected_spelling folder corrected typographic errors in the synthetic letters — but the character offsets in the `.ann` files were generated against the *original, uncorrected* text. When the corrected text is substituted under the same offsets, the source slice no longer matches the stored annotation span.

Examples from the data:
- `EA0008`: ann stores `"sseizures-"` (double-s typo), corrected text has `"seizures"` at the same position
- `EA0013`: ann stores `"Kepra-"`, corrected text has `"Keppra"` (the correct drug name)
- `EA0014`: ann stores `"zobisamide"`, corrected text has `"Zonisamide"`
- `EA0031`: ann stores `"Eplim-"`, corrected text has `"Epilim"`

In every case, the annotation intent is unambiguous — the annotator correctly identified the clinical entity. The stored span text reflects what was actually in the letter at annotation time, and the corrected text is the pedagogically cleaner version. The "mismatch" is between two representations of the same word at different stages of a preprocessing pipeline.

**Implication for the quantitative number:** The 13.5% "boundary issue" rate should not be interpreted as annotation boundary quality. It is an estimate of the rate at which spelling corrections changed the letter text without updating annotation file offsets. The actual annotation quality for span identification is substantially higher.

**Real pipeline impact:** The evaluation uses corrected text but CSV offsets from the pre-correction export. This creates a genuine downstream problem for any offset-dependent scoring (evidence overlap), but it is an engineering issue, not a labelling quality issue.

---

### 1.2 The E2 dose conflicts are almost entirely split-dose prescriptions

**Verdict: schema limitation. Clinical content is correct.**

Epilepsy clinic letters routinely describe asymmetric dosing — a morning dose and an evening dose of the same drug. The ExECT annotation schema has a single `DrugDose` attribute per Prescription annotation. When a letter specifies `"levetiracetam 750mg mane, 500mg nocte"`, the annotator cannot represent both doses in a single annotation, so they create two overlapping annotations with the same drug name span but different dose values.

Direct evidence:
- `EA0007`: Letter says `"levetiracetam 750mg mane, 500mg nocte"`. Two annotations at positions 107–121 (the drug-name span only) with DrugDose=750 and DrugDose=500.
- `EA0019`: Letter says `"Epilim 300 mg in the morning and 600 mg in the evening"`. Two annotations with DrugDose=300 and DrugDose=600.
- `EA0038`: Letter says `"Carbamazepine 400mg/400 mg/200mg"` (TID with asymmetric doses). Two annotations with DrugDose=400 and DrugDose=200.

This pattern is clinically correct. Split dosing is the norm in antiepileptic prescribing — sodium valproate, levetiracetam, carbamazepine are almost always given in split doses, often asymmetric. The annotators handled a schema limitation by using the only available tool: multiple annotations.

**Implication for the quantitative number:** Of the 30 tier-1 numeric conflicts, the great majority are split-dose cases, not genuine conflicts. A genuine conflict would require the same drug to have two incompatible single-dose claims (e.g., one annotation says "100 mg once daily" and another says "200 mg once daily" with no difference in framing). None of the examined cases show this pattern.

**Real pipeline impact:** The evaluation's `medication_full` F1 metric uses set-matching on (name, dose, unit, frequency) tuples. A split-dose drug contributes two gold tuples (levetiracetam at 750 mg and levetiracetam at 500 mg). A model that extracts only the dominant dose will score a false negative on the other entry. This is a genuine evaluation deflation — but it stems from the metric not having a split-dose representation, not from the annotation being wrong.

---

### 1.3 The Diagnosis certainty conflicts are deliberate subspecification uncertainty

**Verdict: schema limitation expressing genuine clinical reasoning. Not an error.**

The 7 Diagnosis certainty conflicts all follow one pattern: a broad diagnosis receives Certainty=5 (certain), while a specific subtype receives Certainty=4 (probable). For example:
- `EA0002`: `focal-epilepsy` at Certainty=5, `temporal-lobe-epilepsy` at Certainty=4
- `EA0004`: `epilepsy` at Certainty=5, `focal-epilepsy` at Certainty=4
- `EA0035`: `epilepsy` at Certainty=5, `generalised-epilepsy` at Certainty=4

This is clinically accurate reasoning. A clinician can be certain a patient has epilepsy while remaining uncertain about the precise syndrome subclassification. The ExECT schema encodes this by allowing multiple overlapping Diagnosis annotations with different certainty values. The audit algorithm classifies these as conflicts because the Certainty attribute differs between overlapping spans — but this is the correct and intended use of the schema.

**Implication:** The certainty-conflict cases do not represent annotation quality problems. They represent an annotation scheme that supports clinical uncertainty modelling more richly than the audit algorithm assumed.

---

### 1.4 The E5 seizure-free vs active contradictions are multiple seizure type annotations

**Verdict: schema limitation. Almost all cases are semantically correct.**

The most instructive case is `EA0056`. The letter describes two distinct seizure types:
- Partial motor seizures (left arm twitching, retained awareness): once per month
- Secondary generalised seizures: once per year, last occurring Christmas 2009

The annotation contains three SeizureFrequency labels on or near the word `"secondary-generalised-seizure"`:
- T22 (positions 620–650): NumberOfSeizures=1, TimePeriod=Year — capturing the yearly rate
- T17 (positions 620–649): NumberOfSeizures=0, DayDate=25, MonthDate=12, YearDate=2009, TimeSince=Since — capturing the date of the last event

These are not contradictions. T17 uses the NumberOfSeizures=0 field not to mean "zero seizures" but to mark the point-in-time of the last seizure (25 December 2009) as a temporal anchor. This is an annotation convention: setting NumberOfSeizures=0 with a TimeSince reference identifies the most recent event date. T22 captures the ongoing rate. Both are clinically correct.

The "contradiction" is an audit algorithm assumption — that NumberOfSeizures=0 always means seizure-free. In the ExECT schema, it can also mean "zero additional seizures since [date of last event]". The two interpretations are used differently: seizure-freedom is encoded differently from last-event dating. The audit did not distinguish these two uses.

**A genuine contradiction would be:** the same seizure type, annotated as both currently active and seizure-free since a recent date, with no temporal scope to separate them. From manual reading of the 20 contradiction cases identified, the majority follow the multi-seizure-type pattern above. A smaller number (~5–8) may represent genuine ambiguity where the letter is unclear about whether a historical rate is still current.

---

### 1.5 E3 generic CUIPhrases on PatientHistory are schema-appropriate

**Verdict: not an error for PatientHistory; a real quality gap for Diagnosis and SeizureFrequency.**

PatientHistory annotations capture the presence of conditions and events in a patient's clinical background — not their specific type. "He has a history of seizures" warrants CUIPhrase=`"seizures"`. The 23.1% generic rate is substantially driven by this entity type, which has the largest annotation count (656) and legitimately uses generic terms.

The real quality gap is on Diagnosis and SeizureFrequency annotations where a generic CUIPhrase obscures the specific clinical concept. For example, where a Diagnosis span is `"focal-to-bilateral-convulsive-seizures"` and the CUIPhrase is `"seizures"` — this loses the seizure-type information that the evaluation metrics depend on. From reading the data, this pattern is less prevalent than the aggregate 23.1% suggests, because much of that rate is PatientHistory.

A focused re-analysis of CUIPhrase quality on Diagnosis and SeizureFrequency annotations only would be more informative. Based on the samples examined, the true problematic rate on these entity types is approximately 10–15%.

---

### 1.6 What the ExECT gold labels actually represent

Setting aside tooling artefacts and schema limitations, the qualitative reading produces a different picture than the quantitative audit numbers suggest.

**The clinical content of ExECT annotations is largely correct.** Annotators correctly identified:
- Epilepsy diagnoses and their subtypes, with appropriate certainty gradations
- Antiepileptic medications with their doses, including split dosing
- Seizure frequencies with temporal anchors
- Investigations and their results
- Patient history items

**The genuine quality problems are narrower than the numbers suggest:**

1. *CUIPhrase under-specification on Diagnosis/SeizureFrequency:* approximately 10–15% of these annotations use a generic term where a specific UMLS concept exists. This is a real precision gap that deflates seizure-type F1 and diagnosis accuracy.

2. *A small number of truly ambiguous seizure-frequency annotations:* perhaps 5–8 documents (2.5–4%) where the letter itself is ambiguous about current vs historical frequency, or where multiple readings of "NumberOfSeizures=0" create a genuine semantic conflict.

3. *The CSV/ann offset pipeline bug:* real and consequential for evidence overlap scoring. Not a labelling quality issue but an engineering issue with the export workflow.

The published inter-annotator agreement of F1=0.73 reflects genuine task difficulty, not annotation incompetence. Reading these letters, there are many legitimate annotation choices. The schema is rich enough to capture clinical complexity, and most annotators appear to have used it correctly.

---

## Part 2: Gan (2026)

### 2.1 The G1 reference mismatches reveal a two-pass annotation workflow, not labelling errors

**Verdict: workflow metadata artefact. Final labels are generally correct.**

The `reference[0]` field was designed to record the label that directly follows from the evidence. The `final label` is the authoritative answer. The 111 cases where reference[0] = "unknown" but the final label is specific represent the expected output of a two-pass labelling process:

1. **Pass 1 (evidence collection):** An annotator reads the letter, extracts evidence quotes, and records an initial label. When the letter is complex, this initial label is often "unknown" — a conservative placeholder.
2. **Pass 2 (analysis computation):** The analysis field is completed, which involves careful calculation from the evidence (explicit arithmetic: "X seizures in Y months = X per Y period"). The final label is then updated to reflect the calculated answer.
3. **reference[0] is not updated:** The initial "unknown" placeholder remains.

Reading the actual cases confirms this. Record 5: reference[0] = "unknown", evidence = "Startle-induced seizures" (vague), analysis calculates "four focal-aware episodes and one focal-impaired awareness spell over six weeks → 4 per 6 weeks". The final label `"4 per 6 week"` is correct and well-supported by the analysis. reference[0] was simply never updated after the analysis was done.

Record 100: reference[0] = "unknown", analysis states "The letter explicitly states: 'two definite generalised tonic-clonic seizures in the last six months.'" The final label `"2 per 6 month"` is a direct, accurate reading of an explicit statement in the letter. The "unknown" in reference[0] is a stale artefact.

**What the 67 "ref_rate_differs" cases represent:** These are more diverse. Some are annotation corrections where the label was refined after the reference was set. Others represent cases where the annotator changed the time window for the calculation between the reference pass and the final pass. These are not false labels — they are iterative refinements.

**The 8 "ref_specific_label_unknown" cases** are the most concerning: reference[0] has a specific rate but the final label is "unknown". These may represent genuine cases where the annotator decided on reflection that the evidence was not specific enough to support the initial concrete label.

**Net quality implication:** G1 mismatches should not be interpreted as label errors at scale. They are primarily evidence of a deliberate multi-pass annotation workflow where reference[0] was not housekept. The 121 "category-changing mismatches" reveal the magnitude of deliberation involved — roughly 8% of labels required enough rethinking to cross a pragmatic category boundary — but the outcome of that deliberation (the final label) is what should be evaluated.

---

### 2.2 The G3 seizure-free precision finding is substantially inflated by false positives

**Verdict: real effect, but much smaller than 95.5%.**

The G3 regex searched for specific numeric durations in the combined evidence + analysis text. In 95.5% of the 132 "seizure free for multiple month/year" cases it found a match. But reading the actual cases reveals the primary source of the match:

**The annotation rules themselves reference "6 months" as a threshold.** Almost every analysis for a seizure-free label contains language like: "To classify as seizure free per the rules, the 6-month criterion must be met" or "This meets the 6-month criterion for seizure freedom." The regex found "6 month" in these rule-invocation sentences, not in descriptions of the actual seizure-free duration.

Examples:
- Record 13: analysis says "6 months" as a rule threshold; the actual seizure-free period runs from "some time after April" to October 2025 (~5 months). The label "multiple month" is arguably correct precisely because the duration is not quite 6 months.
- Record 30: analysis explicitly states "no date of last clinic assessment provided" so the duration cannot be computed. "Multiple month" is appropriate. The "6 month" found is the threshold check.
- Record 70: analysis says "since the last clinic review three months ago." This IS a genuine precision opportunity — the label should arguably be "seizure free for 3 month" not "seizure free for multiple month."

**Genuine precision opportunities exist but are a minority.** Where the evidence or analysis contains a specific non-threshold duration (e.g., "six months" or "three months" as a measured period rather than as a rule threshold), the label should be specific. Reading the cases, genuine opportunities account for roughly 20–35% of the 132 multiple-month/year cases, not 95%.

**The more important observation:** The annotation convention uses "multiple month" as a safe default when the exact duration is not explicitly stated in the letter, even when it could be inferred. This is a conservative annotation policy that prioritises precision over coverage. It is not an error — it is a deliberate epistemic choice to avoid over-inference. The convention creates exact-accuracy losses for models that make the reasonable inference ("no seizures from April to October = ~6 months"), but from the annotation perspective, the measured duration is not in the text.

---

### 2.3 G5 historical language is usually a correct annotation of the most quantified datum

**Verdict: annotation convention, not error. Mostly correct.**

The 41 "historical language" cases in G5 follow a consistent pattern: the letter describes a historical rate with precise numbers and a current state with qualitative terms ("remains stable", "continues to do well"). The annotation captures the historical rate because it is the most precisely quantified datum available.

Example from GAN2762: "Based on her seizure diary prior to current therapy, the pattern has been focal cognitive monthly in frequency. Since commencing her current management plan, the frequency has remained unchanged." The label is `"1 per month"`. This is clinical reasoning: the "unchanged" qualifier makes the historical rate the current rate. The analysis recognises this and labels correctly.

The concern is that "historical language" flags indiscriminately — it catches both (a) genuine cases where a historical rate is used because no current rate exists, and (b) cases where the historical rate is explicitly stated to still apply. The latter are correct annotations.

The 10 "seizure-free conflicts" (analysis mentions seizure-free but label is a rate) are the genuinely concerning G5 subclass. Example from GAN14454: Topiramate was stopped 11 Feb, two seizures followed immediately, then no seizures since — clinic date ~2 months later. The analysis correctly determines this is too short for a "seizure free" label (needs ≥6 months) so labels as `"2 per 2 month"` to represent the immediate post-cessation events. This is the annotation ruleset in action. The "seizure_free_in_analysis" flag is a false positive — the analysis notes the seizure-free period but deliberately doesn't label it as such because the threshold isn't met.

---

### 2.4 G6: The cluster non-finding is the most meaningful result in the Gan audit

**Verdict: confirmed, important, clean.**

29% of Gan letters mention cluster terminology in evidence or analysis. In 0% of those cases does preserving cluster structure change the pragmatic category. This is not a coincidence — it reflects the structure of the pragmatic categories. The infrequent/frequent boundary is at 1.1 seizures per month. Cluster frequency and per-cluster count combine multiplicatively (clusters/month × seizures/cluster). For a cluster label to produce a different pragmatic category than a plain-rate label, the plain rate would need to be in a different category than the cluster total. With the categories as broad as they are (roughly: seizure-free, ≤1/month, >1/month, unknown), this is rare in practice.

What this means for the dissertation: the cluster discussion from the initial 50-sample report was legitimate in identifying a real annotation phenomenon, but it is not an evaluation validity concern at the pragmatic category level. It is a precision difference only.

---

### 2.5 G8: The encoding artefacts are consequential but manageable

**Verdict: real, systematic, not catastrophic for LLM reading.**

82.9% of the 1,500 synthetic letters contain UTF-8 double-encoding artefacts. Reading affected text reveals the pattern: sequences like `"two to three seizures over a 24â€"48 hour period"` (where `â€"` is the corrupted form of an em dash) or `"she has a frequencyÃ‚Â·"` (corrupted mid-word bullet point). The artefacts do not corrupt clinical nouns ("seizure", "month", "focal") — they corrupt punctuation and special characters (em dashes, bullet points, degree symbols).

Modern large language models are highly robust to isolated punctuation corruption. The text remains interpretable to any model trained on real-world internet text, which contains similar encoding errors extensively. The clinical content — drug names, frequencies, dates, diagnosis terms — is not affected.

The more meaningful impact is on `retrieve_frequency_spans()`, which uses regex to match sentences containing frequency-related terms. An em-dash or bullet-point corruption that breaks sentence boundaries can cause the retriever to merge or split sentences incorrectly, degrading span quality. This explains some of the retrieval-highlight vs direct-label gap in the G4 experiments.

**Comparison with real letters:** The Gan paper's Real(300) set would not have these artefacts — real clinic letters use consistent character encoding. This means our evaluation condition is inherently harder than the paper's published benchmark condition, by a small but real margin.

---

## Part 3: Overall Assessment — Label Quality Independent of Quantitative Findings

This section represents a fresh qualitative judgement formed from reading source letters, annotations, and label+analysis pairs, without reference to the quantitative counts.

### ExECT 2 (2025): The labels are better than the numbers suggest

**The annotations demonstrate genuine clinical knowledge.** Reading 40+ letters across the corpus, the annotations consistently:
- Identify the correct seizure types, including subtypes (focal with loss of awareness vs focal without, secondary generalisation)
- Capture the clinically relevant temporal structure (seizures since last clinic, since surgery, since drug change)
- Distinguish between affirmed and negated history items appropriately
- Apply CUI codes that link to the correct UMLS concepts
- Handle multi-drug regimens with split doses competently, even within a schema that doesn't natively support them

**The genuinely low-quality annotations are a small minority.** Reading the tier-1 conflict cases, the Certainty-based Diagnosis conflicts, and the E5 seizure-frequency cases, the number of annotations that make a clinically wrong claim is small — perhaps 20–30 annotations across 200 documents, concentrated in seizure-frequency temporal scope and CUIPhrase specificity.

**The more significant quality gap is in what the annotations do not capture.** The schema is oriented towards entity extraction with normalization. It does not capture:
- The clinical trajectory (improving, stable, worsening)
- The mechanism of action or rationale for medication choices
- The relationship between seizure frequency and medication changes
- Causal attribution (this seizure occurred because the patient missed medication)

These are not annotation errors — they are schema scope limitations. But they mean the ExECT gold standard tests a narrower clinical understanding than clinical NLP might ideally target.

**Grade: B+ (good clinical content, genuine but narrow in scope, affected by tooling issues not quality issues)**

### Gan (2026): The labels are a good-faith application of a principled but demanding ruleset

**The annotation scheme is sophisticated and internally consistent.** The Gan labelling rules create a normalized label format with clear semantics. The analysis fields demonstrate careful clinical reasoning — reading them, the annotators understood seizure physiology, clinic letter conventions, and the practical meaning of seizure frequency in epilepsy management.

**The major quality issue is not errors but rule-induced conservatism.** The "≥6 months for seizure-free" rule and the "use the most recent explicit window" convention produce labels that are mechanically derived from a ruleset rather than from the most clinically natural reading of the letter. This creates systematic patterns:
- A patient seizure-free for 5.5 months is labelled as "multiple month" (technically correct by the rules) even though a clinician would say "approaching 6 months, functionally seizure-free."
- A patient whose letter says "no further events since last clinic, which was 3 months ago" is labelled as "multiple month" because the rule says the interval must be stated in the letter.

These are not errors. They are the correct application of a labelling contract designed for reproducibility. But they create a systematic mismatch with how a clinical reader would naturally characterise the letters, which is what the models are asked to do.

**The reference-field workflow issue is a process quality gap, not a label quality gap.** The annotation process involved deliberation (evidenced by the 8.1% of labels where the annotator crossed a pragmatic category boundary between passes). The final labels reflect the outcome of that deliberation. The process just didn't track its own history cleanly.

**The 31 unparsable labels are a real quality problem.** A label the parser cannot process cannot be evaluated. These need to be fixed or excluded.

**Grade: A− (principled, deliberate, internally consistent; main limitation is rule-induced conservatism and a small number of unparsable labels)**

---

## Part 4: How This Changes the Evaluation Interpretation

### What the quantitative audit overcounted

| Quantitative finding | Overcounted because |
|---------------------|---------------------|
| E1: 13.5% span boundary issues | ~80% are spelling-correction artefacts, not annotation errors |
| E2: 30 tier-1 conflicts in 29 docs | Most are split-dose prescriptions — a schema limitation, not an error |
| E5: 30 SF vs active contradictions | Most are multi-seizure-type annotations for the same letter |
| G3: 95.5% seizure-free imprecision | ~65–80% are false positives from rule-threshold text in analysis |

### What the quantitative audit undercounted or missed

| Unquantified finding | Evidence |
|---------------------|---------|
| CUIPhrase under-specification on Diagnosis/SF specifically | Aggregate 23.1% mixes legitimate PatientHistory with real quality gaps |
| Rule-conservatism creating systematic "precision penalty" | Visible in G5 SF-conflict cases and G3 threshold-text pattern |
| Annotation schema cannot represent split-dose prescriptions | Direct reading of tier-1 conflict cases |
| The annotation deliberation process itself adds noise | 8.1% of Gan labels changed pragmatic category between annotation passes |
| Encoding artefacts affect retrieval more than reading | G8 + G4 retrieval experiment gap |

### Revised evaluation-impact assessment

**ExECT medication_full F1** is deflated by ~5–10 points from split-dose representation, not from annotation errors. The metric should be interpreted as "did the model identify all individual dose instances of each drug" not "did the model identify the drug correctly."

**ExECT seizure-type F1** is deflated by genuine CUIPhrase under-specification on ~10–15% of Diagnosis/SeizureFrequency annotations. This is a real quality issue.

**Gan exact label accuracy** is deflated by the "multiple month/year" precision convention for a genuine but smaller subset than G3 suggested — perhaps 20–40 records (1.3–2.7% of 1,500), not 126. Even these are not errors in the annotation; they are correct applications of a conservative rule that our models are asked to over-ride.

**Gan pragmatic F1** is the most defensible metric. It is minimally affected by the quality issues identified — rule-conservatism, split-dose issues, and reference-workflow housekeeping all have low or zero impact at the pragmatic category level.

---

## Part 5: What Models Should Actually Be Measured Against

The ExECT and Gan gold labels establish a floor, not a ceiling. Models that produce outputs **more specific** than the gold are not necessarily wrong. Two examples where a model would reasonably outscore the gold:

**ExECT medication:** A model that extracts "levetiracetam 750 mg mane, 500 mg nocte" as two medication entries (correct) will match the two gold entries correctly. A model that extracts "levetiracetam 750 mg" (morning dose only) will miss the evening dose. A model that extracts "levetiracetam 625 mg average" will miss both. The gold correctly encodes clinical reality for split-dose drugs; the problem is that the evaluation metric (set matching on full 4-tuples) does not recognise partial split-dose capture as a partial credit.

**Gan seizure-free:** A model that reads "no seizures since the last clinic review three months ago" and outputs `"seizure free for 3 month"` is more informative than the gold label `"seizure free for multiple month"`, and is not wrong. At pragmatic level, both are NS. At exact label level, the model is wrong by the Gan schema convention.

The most honest dissertation framing is: **these gold labels test compliance with a specific annotation schema, not optimal clinical information extraction.** Models that score below gold standard are not necessarily clinically inferior to the annotation; they may be applying a different but equally defensible reading. Models that match gold standard are demonstrably compliant with the annotation contract — a meaningful but bounded claim.

---

*Produced from direct reading of source files: `Gold1-200_corrected_spelling/`, `Json/`, `synthetic_data_subset_1500.json`, and `audit/` CSVs. No quantitative rates from `docs/30_gold_audit_results.md` were taken at face value without checking the underlying examples.*
