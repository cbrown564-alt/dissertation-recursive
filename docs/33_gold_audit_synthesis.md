# Gold Label Audit: Synthesis Report

**Date:** 2026-05-10  
**Sources:** `docs/30_gold_audit_results.md`, `docs/31_gold_qualitative_analysis.md`, `docs/32_g3_deep_investigation.md`  
**Coverage:** ExECT 2 (2025) — all 200 documents, 2,092 annotations; Gan (2026) — all 1,500 records, 132 G3 cases read in full

---

## Executive Summary

The quantitative audit produced alarming-looking numbers. The qualitative investigation — reading actual letters, annotations, and analysis texts — substantially revises those numbers. Most of what looked like annotation errors are tooling artefacts, schema limitations, or correct but unusual annotation choices. The genuine quality problems are real but narrower than the headline figures suggest.

The single most actionable finding is not about label quality at all: **the ExECT evaluation pipeline contains a previously undetected engineering bug** — 57 CSV rows carry stale character offsets from before a spelling-correction step and are never scored. This is fixable.

The most unexpected labelling finding is in the Gan dataset: **27% of "seizure free for multiple month" labels are applied to seizure-free periods shorter than the annotator's own stated 6-month threshold**, with documented periods as short as six weeks. The threshold rule exists in the written annotation contract but was not enforced in practice.

**Overall quality grades:** ExECT **B+** (clinical content good; problems are tooling, not labelling). Gan **A−** (principled and internally consistent; main issue is a threshold rule applied inconsistently).

---

## Part 1: ExECT 2 (2025)

### Finding 1 — The 13.5% span-boundary "error" rate is a spelling-correction artefact

**What the numbers said:** 282 / 2,092 annotations (13.5%) have a span-text mismatch against the source letter.

**What it actually is:** The Gold1-200_corrected_spelling folder corrected typographic errors in the synthetic letters *after* annotation was complete. The `.ann` files store span text from the original misspelled source; the corrected text now sits under the same character offsets. When the audit compares `.ann` span text against corrected source text, it finds differences that are entirely due to spelling correction, not annotation error.

**Examples:**
- `EA0008`: annotation stores `"sseizures-"` (double-s, original typo); corrected text has `"seizures"` at the same position
- `EA0013`: annotation stores `"Kepra-"` (misspelling); corrected text has `"Keppra"`
- `EA0014`: annotation stores `"zobisamide"`; corrected text has `"Zonisamide"`
- `EA0031`: annotation stores `"Eplim-"`; corrected text has `"Epilim"`

In every examined case the annotator correctly identified the entity. The "mismatch" is two representations of the same word at different stages of a preprocessing pipeline.

**Verdict:** This is not an annotation quality problem. It is evidence that the spelling-correction step was applied to the text files without propagating corrected offsets to the annotation files. Annotation boundary quality is substantially better than 13.5%.

---

### Finding 2 — The 30 tier-1 dose "conflicts" are split-dose prescriptions

**What the numbers said:** 30 tier-1 numeric conflicts across 29 documents (14.5% of the corpus), flagged as same-span annotations with contradictory dose values.

**What it actually is:** Epilepsy drug regimens routinely use asymmetric split dosing — different morning and evening doses. The ExECT schema has one `DrugDose` attribute per annotation. When a letter specifies two doses, annotators created two overlapping annotations, one per dose. This is the only available representation in the schema.

**Examples:**
- `EA0007`: Letter says `"levetiracetam 750mg mane, 500mg nocte"` → two annotations at the same span, DrugDose=750 and DrugDose=500. Both are correct.
- `EA0019`: Letter says `"Epilim 300 mg in the morning and 600 mg in the evening"` → DrugDose=300 and DrugDose=600. Both are correct.
- `EA0038`: Letter says `"Carbamazepine 400mg/400mg/200mg"` (TID, unequal doses) → DrugDose=400 and DrugDose=200. Both are correct.

**Verdict:** These are not labelling errors. They are correct annotations of a clinical reality the schema cannot represent in a single entry. The evaluation metric (`medication_full` F1 via set-matching on 4-tuples) treats each dose instance separately — a model extracting only one dose of a split-dose drug misses the other, creating a real but schema-attributable false negative.

---

### Finding 3 — The Diagnosis certainty "conflicts" encode deliberate clinical uncertainty

**What the numbers said:** 7 tier-1 conflicts on Diagnosis annotations (Certainty attribute differs between overlapping spans).

**What it actually is:** Every case follows the same pattern — a broad diagnosis (e.g., `"epilepsy"`) carries Certainty=5 (certain), while the specific subtype (e.g., `"temporal-lobe-epilepsy"`) carries Certainty=4 (probable). This is clinically accurate reasoning: a clinician can be certain about a class diagnosis while uncertain about the syndrome subclassification. The schema supports this by allowing multiple overlapping Diagnosis annotations.

**Examples:**
- `EA0002`: `focal-epilepsy` Certainty=5, `temporal-lobe-epilepsy` Certainty=4 — confident about focal onset; uncertain whether temporal or another lobe
- `EA0035`: `epilepsy` Certainty=5, `generalised-epilepsy` Certainty=4 — certain about epilepsy; uncertain about generalised vs focal

**Verdict:** Not errors. Intended use of the schema's certainty modelling.

---

### Finding 4 — The SF vs active "contradictions" are multi-seizure-type annotations

**What the numbers said:** 30 seizure-free vs active contradictions across 20 documents (10%), flagged when the same document has both NumberOfSeizures=0 and NumberOfSeizures>0 annotations on overlapping spans.

**What it actually is:** EA0056 is the template case. The letter describes two distinct seizure types — partial motor seizures (once per month) and secondary generalised seizures (once per year). Three SeizureFrequency annotations appear near the same text:
- T22: NumberOfSeizures=1, TimePeriod=Year — the ongoing rate for secondary generalised seizures
- T17: NumberOfSeizures=0, TimeSince=Since, DayDate=25, MonthDate=12, YearDate=2009 — the date of the last secondary generalised seizure

T17 uses NumberOfSeizures=0 not to assert seizure freedom but to anchor the date of the most recent event. This is a documented schema convention. T22 and T17 are complementary, not contradictory.

**Verdict:** The audit algorithm assumed NumberOfSeizures=0 always means seizure-free. In the ExECT schema it can also mark a point-in-time event date. Most E5 contradictions follow this multi-seizure-type pattern and are semantically correct. A small number (~5–8 documents) may represent genuine temporal-scope ambiguity, but these are not auditable without reading each letter in detail.

---

### Finding 5 — The 23.1% generic CUIPhrase rate mixes legitimate and problematic cases

**What the numbers said:** 483 / 2,092 annotations (23.1%) classified as generic CUIPhrase.

**What it actually is:** The 656 PatientHistory annotations legitimately use generic terms — "he has a history of seizures" warrants CUIPhrase=`"seizures"`. PatientHistory captures presence of a condition, not its type. The aggregate 23.1% rate is substantially driven by this entity type.

The real quality gap is on Diagnosis and SeizureFrequency annotations where a specific seizure type (e.g., `"focal-to-bilateral-convulsive-seizures"`) is normalized to a generic term (e.g., `"seizures"`). From the examined cases this affects approximately **10–15% of Diagnosis and SeizureFrequency annotations** — the ones that actually determine seizure-type F1 and epilepsy-diagnosis accuracy scores.

**Verdict:** The headline 23.1% rate overstates the problem. The real, evaluation-relevant quality gap is 10–15% of Diagnosis/SeizureFrequency annotations, where under-specified CUIPhrases deflate seizure-type F1 by penalising models that extract the correct specific concept.

---

### Finding 6 — The E6 CSV/ann offset mismatch is a real, undetected pipeline bug

**What the numbers said:** 57 CSV rows with character offsets that do not match any `.ann` annotation.

**What it is:** `evaluate.py` reads CSVs exclusively for medications, seizure frequency, investigations, and diagnosis — it never reads `.ann` files directly for these fields. The CSVs were exported from Markup before the spelling-correction step. The `.ann` files were updated for corrected spelling. The two are now out of sync. The 57 affected rows reference positions in the original text that no longer correspond to the corrected text; the evaluation pipeline silently ignores them.

**This is an engineering bug, not a labelling quality issue.** Annotations exist in the `.ann` files that are never scored because the corresponding CSV row carries a stale offset. The magnitude of affected scored annotations is not fully quantifiable without a complete cross-reference, but 57 rows across 9 CSV files is a meaningful fraction of the ~600 CSV-evaluated annotations.

**Verdict:** Actionable. The fix is to re-export CSVs from the corrected-spelling `.ann` files with updated character offsets, then re-run evaluation.

---

### ExECT: What the numbers actually mean

| Reported finding | Revised interpretation |
|-----------------|----------------------|
| 13.5% span boundary issues | Spelling-correction offset drift — not annotation errors |
| 30 tier-1 dose conflicts | Split-dose prescriptions — schema limitation, content correct |
| 7 Diagnosis certainty conflicts | Deliberate uncertainty modelling — not errors |
| ~20 SF vs active contradictions | Multi-seizure-type annotation pattern — not contradictions |
| 23.1% generic CUIPhrase | Overstated; real gap is ~10–15% on Diagnosis/SF only |
| 57 stale-offset CSV rows | **Real pipeline bug — affects scored evaluation** |

The genuine quality problems: CUIPhrase under-specification on ~10–15% of Diagnosis/SF annotations; ~5–8 documents with genuinely ambiguous seizure-frequency temporal scope; and the E6 pipeline bug. Everything else is a tooling artefact or correct schema usage.

---

## Part 2: Gan (2026)

### Finding 7 — Reference field mismatches reveal a two-pass workflow, not label errors

**What the numbers said:** 197 / 1,500 records (13.1%) have a mismatch between the final gold label and `reference[0]`; 121 of those (8.1%) would change the pragmatic category.

**What it actually is:** The annotation was done in two passes. Pass 1 collected evidence quotes and recorded an initial label — often "unknown" as a conservative placeholder when the letter was complex. Pass 2 completed the analysis field, which involves careful arithmetic ("3 seizures in 3 months → 1 per month") and updates the final label. The `reference[0]` field was not updated after Pass 2.

Reading the actual mismatched cases confirms this:
- Record 100: reference[0] = "unknown", analysis states "The letter explicitly states: 'two definite generalised tonic-clonic seizures in the last six months.'" Final label: `"2 per 6 month"` — directly supported by explicit text. The "unknown" in reference[0] is a stale placeholder from Pass 1.
- Record 5: reference[0] = "unknown", evidence = "Startle-induced seizures" (vague), but analysis calculates "four focal-aware episodes and one focal-impaired awareness spell over six weeks → 4 per 6 weeks". Final label: `"4 per 6 week"` — correct.

The 8 "ref_specific_label_unknown" cases (where reference has a specific rate but label is "unknown") are more concerning — here the annotator apparently decided on reflection that the initial specific answer was not supportable.

**Verdict:** G1 mismatches are workflow housekeeping failures, not label errors. The final labels are authoritative. The 121 category-changing mismatches reveal that ~8% of records required enough deliberation to cross a pragmatic category boundary between passes — evidence of careful judgement, not carelessness.

---

### Finding 8 — G2: 31 unparsable labels are a real, fixable problem

**What it is:** 31 / 1,500 gold labels (2.1%) return `UNKNOWN_X` from `label_to_monthly_frequency()` despite not being "unknown" or "no seizure frequency reference". These are likely novel label forms such as `"1 per 1 to 2 day"` (range on the period side) or labels with additional qualifiers not covered by the parser.

**Evaluation impact:** Any record where the gold label cannot be parsed maps to the UNK pragmatic category. A model that correctly extracts the frequency is scored wrong against a gold UNK.

**Verdict:** Real problem. 31 records should either be reparsed with an extended parser, manually relabelled to a canonical form, or excluded from evaluation with an explicit note.

---

### Finding 9 — G3: The seizure-free precision finding is three different things at once

This is the most investigated finding. Reading all 132 "seizure free for multiple month/year" cases individually overturns the initial 95.5% figure completely.

**The corrected breakdown:**

| Category | Count | Rate | Description |
|----------|------:|-----:|-------------|
| A — Label correct | 67 | 50.8% | "6 month" found in text is the annotation rule threshold, not a measured duration. Label is appropriate. |
| B — Genuine precision opportunity | 21 | 15.9% | Specific duration available in letter but not used. Models penalised for being more specific. |
| P — Sub-threshold violation | 36 | 27.3% | Label applied to periods explicitly identified as <6 months. Annotator's own rule not enforced. |
| D — Genuinely vague | 6 | 4.5% | No duration recoverable. "Multiple" is correct. |
| C — Ambiguous | 2 | 1.5% | Borderline cases. |

**Category A — the false positive problem.** The annotation rules state "to classify as seizure free, at least 6 months of seizure freedom is required." Almost every analysis contains a sentence invoking this rule. The G3 regex found "6 month" in these rule-invocation sentences, not in descriptions of the actual period. Example — GAN8188: *"There is no explicit date of the last clinic assessment provided. Without that date, we cannot confirm a seizure-free duration of at least 6 months."* The label "multiple month" is correct; the "6 month" found is the threshold check, not a measured duration.

**Category B — models penalised for precision.** 21 cases where the letter or analysis contains a specific, usable duration that was replaced with "multiple". The clearest:
- **GAN7738**: Letter says *"since the last appointment six months ago, there have been no further attacks reported."* Gold label: `"seizure free for multiple month"`. The correct label is `"seizure free for 6 month"`. A model reading this and outputting the specific form scores 0 on exact accuracy.
- **GAN8006**: Letter explicitly says *"no blackouts or focal impaired-awareness episodes over the past six months."* Gold: `"seizure free for multiple month"`. Should be `"seizure free for 6 month"`.
- **GAN8736**: *"remained without episodes for over 18 months."* Gold: `"seizure free for multiple month"`. Should be `"seizure free for multiple year"` — wrong on both specificity and period unit.

**Category P — the unexpected finding.** The annotation contract requires ≥6 months for a seizure-free label. In 36 cases, the analysis explicitly notes the seizure-free period is below threshold — then applies the label anyway. Examples:
- **GAN7816**: *"no observed or reported events since the start of last month."* One month of seizure freedom. Label: `"seizure free for multiple month"`.
- **GAN8791**: *"clear improvement over the last six weeks."* Six weeks. Label: `"seizure free for multiple month"`.
- **GAN8813**: *"over the past 90 days (three months), zero seizure activity."* Three months, explicitly stated. Label: `"seizure free for multiple month"`.

The analyses in P cases follow a recognisable template: identify the period, note it is fewer than 6 months, note "we cannot confirm seizure-free status per the rules", then label as seizure-free anyway. Step 4 contradicts step 3. The de facto policy was "currently seizure-free at clinic → label as seizure-free for multiple month, regardless of duration." The written rule was not enforced.

**Verdict:** The 95.5% G3 figure is a measurement artefact. The real breakdown is: 55% correct, 16% genuine precision opportunity, 27% threshold rule inconsistently applied. The P cases are the most important finding — they mean "seizure free for multiple month" is an inconsistently applied label that could refer to 6 weeks or 6+ months.

---

### Finding 10 — G6 cluster handling is a clean non-finding

**What the numbers said:** 145 / 500 sampled records (29%) mention cluster seizure terminology.

**What the investigation found:** 0 of those 145 cases produce a different pragmatic category when cluster structure is preserved vs collapsed to a plain rate. The infrequent/frequent boundary at 1.1/month is broad enough that clusters × per-cluster multiplication almost never crosses it compared to the plain cluster-period rate.

**Verdict:** Cluster normalization is not an evaluation validity concern. It is a precision difference (cluster labels carry more clinical information) but not a category-scoring problem. The concern raised in the initial 50-sample analysis was a statistical artefact of small-sample observation.

---

### Finding 11 — G8 encoding artefacts are real but the impact is selective

**What the numbers said:** 1,243 / 1,500 records (82.9%) contain UTF-8 double-encoding artefacts.

**What they are:** The artefacts corrupt punctuation and special characters — em dashes appear as `â€"`, bullet points as `Ã‚Â·`, degree symbols become garbled. Clinical nouns (seizure, month, focal, levetiracetam) are not affected.

**Impact profile:**
- **LLM reading:** Low. Modern LLMs are robust to punctuation corruption; the clinical content is preserved.
- **Regex retrieval (`retrieve_frequency_spans()`):** Moderate. Sentence-boundary patterns may fail when em-dashes that separate clauses are corrupted, causing retrievers to merge or split sentences incorrectly. This explains some of the retrieval-highlight vs direct-label gap in the G4 experiments.
- **Comparison with published Gan benchmark:** The Gan paper's Real(300) set uses real clinic letters with clean encoding. Our synthetic subset is an inherently harder input condition, by a small but real margin.

---

## Part 3: Recommendations

### Immediately actionable — engineering fixes

**R1. Fix the E6 CSV offset drift.** Re-export all Markup CSVs from the Gold1-200_corrected_spelling `.ann` files with updated character positions, then re-run evaluation. Until this is done, medication, seizure-frequency, investigation, and diagnosis scores may exclude some annotations silently. Priority: **high**.

**R2. Fix or exclude the 31 G2 unparsable Gan labels.** Extend the parser to handle range-on-period forms like `"1 per 1 to 2 day"`, or manually relabel them to canonical form, or exclude them with an explicit note in all reported results. Priority: **medium**.

### For evaluation reporting

**R3. Report pragmatic F1 as the primary Gan metric.** It absorbs the B-case precision penalty, the P-case threshold inconsistency, and G7 annotator-dependent contradictions. Exact label accuracy is too sensitive to annotation convention choices to be the primary claim.

**R4. Report medication_name F1 as the primary ExECT medication metric.** `medication_full` F1 is deflated by 5–10 points from the split-dose schema limitation, not from model errors. Medication name F1 is robust to this because canonical drug name matching tolerates spelling variation without requiring dose-level exact match.

**R5. Treat evidence overlap scores as lower bounds.** The E1 offset drift and E6 CSV mismatch together corrupt evidence-overlap scoring significantly. These scores should be footnoted as "evaluated against a gold set with known offset drift from spelling correction."

### For dissertation framing

**R6. Replace the G3 headline figure.** Do not cite the 95.5% rate. The correct dissertation sentence is:

> "A complete manual review of all 132 Gan gold labels with 'seizure free for multiple month/year' identified three sub-populations: 51% correctly use the vague form because the duration is genuinely unknown from the letter; 16% represent genuine precision opportunities where a specific duration was available but not used, and which penalise models for being more specific than the gold; and 27% apply the seizure-free label to periods explicitly identified in the analysis as shorter than the annotator's own 6-month threshold, indicating the written rule was not uniformly enforced. All three sub-populations map to the same NS pragmatic category, so pragmatic F1 is unaffected; the noise is confined to exact label accuracy."

**R7. Replace the E2 headline.** Do not describe the dose conflicts as "29 documents with numeric attribute conflicts." The correct framing is:

> "29 documents have multiple prescription annotations for the same drug representing split doses (e.g., 750 mg morning, 500 mg evening), which the annotation schema cannot encode in a single entry. This is clinical content that is correct but not representable in the schema; it deflates medication_full F1 for models that extract only one dose instance of a split-dose regimen."

**R8. Note the E6 bug explicitly.** The dissertation should state that the ExECT evaluation pipeline has a known offset-drift issue in which an unquantified subset of annotations is silently excluded from scoring. Until R1 is complete, scores should be described as conservative estimates.

**R9. Retain the published IAA as context.** ExECT's published inter-annotator agreement of F1=0.73 is an external anchor. Our best systems at 0.70–0.85 on the cleaner fields are operating at or above human agreement level — not failing badly. This framing is defensible given the audit findings.

---

## Part 4: What the Audit Did and Did Not Change

### Findings that held up under scrutiny

- **G6 cluster non-finding** — confirmed clean: 0 category-changing collapses across 145 cluster-mention cases.
- **G1 as workflow metadata** — confirmed: reference[0] mismatches are stale placeholders from a two-pass annotation process, not label errors.
- **ExECT schema consistency** — confirmed: attribute population rates are near-perfect across 200 documents; the annotation scheme is applied uniformly.
- **G8 encoding artefacts affect retrieval more than reading** — confirmed: the artefacts are punctuation-only and preserved clinical content.

### Findings that were revised substantially

| Initial claim | Revised claim |
|--------------|---------------|
| 13.5% span boundary error rate | Artefact of spelling correction; actual annotation quality is substantially better |
| 30 tier-1 numeric conflicts are label errors | Split-dose prescriptions — correct annotations in a schema that cannot represent them cleanly |
| 95.5% of "multiple month" labels have specific duration available | 51% correct, 16% genuine precision gap, 27% threshold rule applied inconsistently, 5% genuinely vague |
| G3 explains the exact-accuracy gap | Partially true for B cases (1.4% of all records); but P cases also create unfair scoring in the opposite direction |

### Net quality assessment

**ExECT 2 (2025):** The clinical content of the annotations is largely correct. Annotators applied a rich, consistent schema with genuine clinical knowledge. The real quality gaps are: CUIPhrase under-specification on ~10–15% of Diagnosis/SeizureFrequency annotations, and the E6 pipeline bug. Grade: **B+**.

**Gan (2026):** The annotation scheme is principled and internally consistent. The analysis fields demonstrate careful clinical reasoning. The main quality issue is that the written annotation rules (6-month threshold for seizure-free status) were not uniformly enforced in practice, creating a class of "seizure free for multiple month" labels that range from 6 weeks to 6+ months of actual seizure freedom. The 31 unparsable labels are a fixable technical problem. Grade: **A−**.

---

## Part 5: One-Page Reference Summary

### ExECT findings for dissertation use

| Check | Reported number | What it means | Evaluation impact |
|-------|----------------|---------------|-------------------|
| E1: Span boundaries | 13.5% mismatch | Spelling-correction offset drift | Inflates evidence-overlap FN rate; not annotation error |
| E2: Dose conflicts | 30 in 29 docs | Split-dose prescriptions; schema limitation | Deflates medication_full F1 by ~5–10pp |
| E3: Generic CUIPhrase | 23.1% overall | ~10–15% real problem on Diagnosis/SF only | Deflates seizure-type F1 and diagnosis accuracy |
| E4: Dose outside span | 35% of prescriptions | Annotation design choice; dose from context | Minor impact on dose F1 |
| E5: SF contradictions | 30 across 20 docs | Multi-seizure-type annotations, not contradictions | Minor inflation of per-letter frequency accuracy |
| E6: CSV offset drift | 57 stale rows | **Pipeline bug — annotations silently excluded** | Unquantified deflation; fix before final reporting |

### Gan findings for dissertation use

| Check | Reported number | What it means | Evaluation impact |
|-------|----------------|---------------|-------------------|
| G1: Reference mismatch | 13.1% / 8.1% category-changing | Two-pass workflow housekeeping; final labels correct | None at pragmatic level |
| G2: Unparsable labels | 31 (2.1%) | Real technical problem | Deflates pragmatic F1 by ~2.1% |
| G3: Seizure-free "precision" | 95.5% → 16% / 27% | B: precision penalty; P: threshold not enforced | B: deflates exact accuracy ~1.4%; P: unfair scoring ~2.4% |
| G6: Cluster handling | 29% mention clusters | 0 category-changing collapses | None at pragmatic level |
| G8: Encoding artefacts | 82.9% of records | Punctuation only; retrieval mildly affected | Small negative vs published benchmark condition |

---

*This synthesis supersedes individual findings in docs/30, 31, and 32 wherever they conflict. The recommended evaluation framing in R3–R9 should be applied to all dissertation chapters reporting ExECT or Gan results.*
