# Gold Label Audit Plan

**Date:** 2026-05-10  
**Purpose:** Full quantitative and qualitative audit of both gold-standard datasets to characterise label quality, quantify error rates, and produce defensible dissertation-ready caveats.  
**Scope:** All 200 ExECT 2 (2025) gold labels; 500 stratified records from Gan (2026).

---

## Background and Motivation

The initial 20-document ExECT sample and 50-document Gan sample (see `docs/28_gold_label_quality_analysis.md`) revealed systematic labelling problems in both datasets. A preliminary query on the full Gan dataset found that 197/1,500 records (13.1%) have a mismatch between the final label and `reference[0]` — substantially higher than the 8% rate observed in the 50-document sample. This audit will scale those findings to the full datasets and produce quantified, reproducible error rates.

**Cluster normalization note:** After discussion, the key question for seizure frequency is whether a cluster day is correctly identified as a seizure day — not whether the exact within-cluster count is known. A label of `"1 per 3 day"` (one cluster period every 3 days) is acceptable even if the gold label uses `"1 cluster per 3 day, N per cluster"`. The cluster-vs-plain-rate distinction is worth flagging as a secondary finding but should not be treated as a primary error for Gan category scoring purposes, since both typically map to the same pragmatic bin.

---

## Part 1: ExECT 2 (2025) Full Audit (n=200)

### Data sources

| Source | Description |
|--------|-------------|
| `data/ExECT 2 (2025)/Gold1-200_corrected_spelling/EA*.ann` | 200 annotation files (primary gold) |
| `data/ExECT 2 (2025)/Gold1-200_corrected_spelling/EA*.txt` | 200 corresponding letter texts |
| `data/ExECT 2 (2025)/MarkupOutput_200_SyntheticEpilepsyLetters/*.csv` | 9 derived CSV files used in evaluation |

The `.ann` files are the primary source. The CSVs are derived from Markup export and are what `evaluate.py` actually reads — any discrepancy between `.ann` and CSV is itself an evaluation pipeline bug.

### Check catalogue

#### E1: Span-boundary integrity (programmatic, all 200 files)

For every `T{id} EntityType start end\tspan_text` line in each `.ann` file:

1. Open the corresponding `.txt` file and read `text[start:end]`.
2. Normalise both strings (strip whitespace, lowercase) and compare.
3. **Exact match**: record as clean.
4. **Off-by-one match**: text[start-1:end] or text[start:end+1] matches — record as boundary-shifted.
5. **Truncated**: the span text is a prefix of the source text at that position — record as truncated with missing-char count.
6. **Leading separator**: span text starts with `-`, `–`, `,` — record.
7. **No match**: record as severe (likely an export error or post-annotation edit).

**Output:** `audit/exect/E1_span_boundary.csv` — one row per annotation with columns: `doc_id`, `entity_id`, `entity_type`, `start`, `end`, `span_text`, `source_text`, `issue_type`, `severity`.

**Expected findings:** Based on the 20-doc sample, ~23% of annotations will have trailing/leading hyphen or truncation. Confirm rate and distribution across entity types.

#### E2: Duplicate and conflicting label detection (programmatic, all 200 files)

For each document, for each entity type, identify pairs of annotations where:

- Spans overlap by >50% (by character overlap).
- Attribute values differ (e.g., two Prescription labels on the same drug with different `DrugDose`).

Conflict severity tiers:
- **Tier 1 (high)**: Same span, contradictory numeric attribute (dose, seizure count, onset age).
- **Tier 2 (medium)**: Overlapping spans, different CUIPhrase — possible split or duplication error.
- **Tier 3 (low)**: Exact same span and same entity type with identical attributes — true duplicate (no harm, just redundancy).

**Output:** `audit/exect/E2_duplicates_conflicts.csv`

**Special sub-check:** For SeizureFrequency: flag any case where the same span is labelled with both `NumberOfSeizures: 0` (seizure-free) and `NumberOfSeizures: N > 0` (active seizures).

#### E3: CUIPhrase specificity classification (programmatic + spot review)

Collect every `CUIPhrase` value across all 200 files. Classify each as:

- **Specific**: full clinical concept term (e.g., `focal-seizures-with-loss-of-awareness`, `lamotrigine`, `temporal-lobe-epilepsy`).
- **Generic**: single-word anatomical or class term that loses clinical meaning (e.g., `focal`, `generalised`, `drug`, `brain`, `transient`, `occipital`).
- **Malformed**: contains parentheses, hyphens only, or is clearly a truncated phrase (e.g., `occipital-lobe)-epilepsy`).
- **Missing**: CUIPhrase attribute absent.

**Output:** `audit/exect/E3_cuiphrase_quality.csv` — per annotation with classification. Summary: count and rate by entity type.

Flag every entity type × CUI category cell where >10% of annotations are generic or malformed — these are the cells most likely to generate false negatives during evaluation.

#### E4: Medication attribute completeness and internal consistency (programmatic)

For every `Prescription` annotation across all 200 files:

1. **DrugName presence and canonicality**: compare DrugName against `canonical_medication_name()` from `normalization.py`. Flag if they differ significantly.
2. **DrugDose presence**: record if absent; check if the span text itself contains a number consistent with the dose.
3. **DoseUnit presence**: record if absent.
4. **Frequency presence**: record if absent.
5. **Span-dose consistency**: does the span text contain the stated dose number? Flag cases where dose is stated in attributes but absent from span (requires external context).

Separately: identify all documents with multiple Prescription annotations for the same canonical drug name; for those, check if doses are consistent or contradictory.

**Output:** `audit/exect/E4_prescriptions.csv` — one row per Prescription annotation with all attribute checks.

#### E5: SeizureFrequency attribute completeness and temporal consistency (programmatic + manual review)

For every `SeizureFrequency` annotation:

1. **Numeric population**: are `NumberOfSeizures` or (`LowerNumberOfSeizures` + `UpperNumberOfSeizures`) populated?
2. **TimePeriod + NumberOfTimePeriods**: are both populated when a rate is implied?
3. **Temporal scope**: is one of `PointInTime`, `TimeSince_or_TimeOfEvent`, or `FrequencyChange` populated to anchor the frequency?
4. **CUIPhrase consistency with co-occurring Diagnosis span**: where the same surface text has both Diagnosis and SeizureFrequency labels, do they share the same CUI/CUIPhrase?
5. **Seizure-free vs active contradiction**: if the same document has both a `NumberOfSeizures: 0` annotation and an active frequency annotation, is the temporal scope clearly different?

**Manual review sample:** For E5 findings flagged as tier 1 conflicts, read the source letter to determine whether the conflict is resolvable from context.

**Output:** `audit/exect/E5_seizure_frequency.csv`

#### E6: CSV vs .ann consistency (programmatic)

The evaluation pipeline reads CSVs (`MarkupPrescriptions.csv`, `MarkupSeizureFrequency.csv`, etc.), not `.ann` files directly. Verify that:

1. Every `.ann` Prescription annotation appears in `MarkupPrescriptions.csv` with matching character offsets.
2. Every `.ann` SeizureFrequency annotation appears in `MarkupSeizureFrequency.csv`.
3. Every `.ann` Diagnosis annotation with `Negation: Affirmed` and `DiagCategory: Epilepsy` appears in `MarkupDiagnosis.csv`.
4. No CSV rows reference files or offsets not present in the `.ann` set.

**Output:** `audit/exect/E6_csv_ann_consistency.csv` — rows flagging mismatches with detail.

#### E7: Cross-document annotation consistency (programmatic)

Check that the annotation scheme is applied consistently across the 200 documents:

1. **Negation population rate** by entity type: is `Negation` always present for Diagnosis, PatientHistory? Flag any entity type where >5% of annotations lack Negation.
2. **Certainty population rate**: same analysis.
3. **CUI population rate**: what fraction of annotations lack a CUI entirely?
4. **Entity type frequency distribution**: are some documents annotated with significantly fewer entities than average? Flag outliers (>2 SD below mean entity count) for spot review.

**Output:** `audit/exect/E7_cross_doc_consistency.csv`

#### E8: Source-letter quality checks (programmatic)

For each `.txt` file:

1. Check for encoding artefacts: `Ã`, `ï¿½`, `â€`, `Â` sequences.
2. Check for pronoun/sex inconsistencies: does the same letter use both "he/his" and "she/her"?
3. Check for structurally incomplete letters: no greeting, no sign-off, very short (< 200 characters).

**Output:** `audit/exect/E8_letter_quality.csv`

---

## Part 2: Gan (2026) Audit (n=500 stratified)

### Data source

`data/Gan (2026)/synthetic_data_subset_1500.json` — 1,500 records.

### Sampling strategy

Draw a stratified sample of 500 records across the pragmatic category distribution of gold labels, to ensure proportional representation:

| Category | Full-dataset N (approx.) | Sample N |
|----------|--------------------------|----------|
| UNK (unknown / no reference) | ~233 (16%) | 80 |
| NS (seizure-free) | ~190 (13%) | 65 |
| infrequent (>0 to ≤1.1/month) | ~520 (35%) | 175 |
| frequent (>1.1 to 999/month) | ~557 (37%) | 180 |
| **Total** | 1,500 | **500** |

Within each stratum, sample randomly. Include all 197 reference-mismatch records proportionally (they are flagged in G1 below and will be over-represented in the manual review phase).

**Note:** All 1,500 records can be audited programmatically for checks G1–G4. The 500-record cap applies to the labour-intensive checks (G5–G7) that require reading the full letter and analysis.

### Check catalogue

#### G1: Reference field consistency (programmatic, n=1,500)

Already run: 197/1,500 records (13.1%) have `label != reference[0]`. 

For the full 1,500:

1. For each record, compare `final_label` (normalized) with `reference[0]` (normalized).
2. Classify the mismatch type:
   - `ref_unknown_label_specific`: reference says `unknown`, label is a specific rate or seizure-free.
   - `ref_specific_label_unknown`: reference has a value, label is `unknown`.
   - `ref_seizure_free_label_rate`: reference says `seizure free`, label is a rate.
   - `ref_no_ref_label_something`: reference says `no seizure frequency reference`, label differs.
   - `ref_rate_differs`: both are rates but numeric values differ.
3. Assess label vs reference: which is better supported by `reference[1]` (the evidence quote)?

**Output:** `audit/gan/G1_reference_consistency.csv` — one row per mismatch record (197 rows), with mismatch type, both values, and evidence quote.

**Key question:** Do the reference mismatches systematically bias the evaluation in one direction? (e.g., does the gold label tend to be more specific than reference, or vice versa?)

#### G2: Label parsability and category consistency (programmatic, n=1,500)

For every gold label:

1. Run through `label_to_monthly_frequency()` from `gan_frequency.py`.
2. If result is `UNKNOWN_X` but label is not `"unknown"` or `"no seizure frequency reference"`, flag as **unparsable label** — these are either novel label forms or malformed strings.
3. Compute `pragmatic_category` and `purist_category` for every label.
4. Flag any label that produces a category that seems inconsistent with the label text (e.g., a seizure-free label that maps to `frequent` due to parse error).

**Output:** `audit/gan/G2_label_parsability.csv`

#### G3: Seizure-free precision audit (programmatic, n=1,500)

Collect all records where the gold label is `"seizure free for multiple month"` or `"seizure free for multiple year"`.

For each, check `reference[1]` (evidence quote) and `analysis` for a specific numeric duration:

- Regex patterns: `\d+\s*month`, `\d+\s*year`, `\d+\s*week`, written numbers (six, twelve, etc.).
- If a specific duration is present in the evidence/analysis, flag as **precision opportunity**: the label could be more specific than `"multiple"`.

**Output:** `audit/gan/G3_seizure_free_precision.csv` — with the specific duration found, if any.

**Key metric:** How many of the `seizure free for multiple month/year` labels (count from G2) have a specific duration available but unused? This quantifies how many exact-accuracy failures are gold imprecision rather than model error.

#### G4: "Multiple" as count vs duration (programmatic, n=1,500)

Separate from G3: collect all labels containing `"multiple per"` (as a seizure count, not a duration). These are valid labels per the Gan scheme.

For each, check whether the analysis/evidence contains a specific number that was deliberately abstracted to "multiple" or a number that should have been used. Flag cases where a specific count (e.g., "5–7 per week") was rounded to "multiple per week".

**Output:** `audit/gan/G4_multiple_count_audit.csv`

#### G5: Analysis-to-label consistency (manual + programmatic, n=500)

For each of the 500 sampled records, parse the `analysis` field and verify:

1. **Arithmetic consistency**: Where the analysis states "X seizures over Y months → X per Y month", verify the label matches the stated calculation. Flag arithmetic errors.
2. **Current vs historical frequency**: Where the analysis distinguishes current and historical frequency and chooses current, verify the label reflects the current one. Flag if label appears to reflect historical data.
3. **Seizure-free override**: Where the analysis states "seizure-free since [date], and this is within a threshold for seizure-free labelling", verify the label is seizure-free and not a rate.
4. **Ambiguity acknowledgement**: Where analysis notes uncertainty but label is specific, flag for review.

This check is partly automated (arithmetic extraction via regex) and partly requires reading the analysis text.

**Output:** `audit/gan/G5_analysis_consistency.csv` — one row per record, with: `label`, `analysis_stated_rate`, `match`, `issue_type`, `notes`.

#### G6: Cluster handling review (programmatic + spot review, n=500)

For the 500-sample, identify records where `reference[1]` or `analysis` contains cluster-related terms: `cluster`, `batch`, `burst`, `group of seizures`, `series`.

For each cluster-mention case:
1. Does the gold label use the cluster format (`"N cluster per period, M per cluster"`)?
2. If not, does the plain-rate label still map to the same pragmatic category as a reasonable cluster interpretation?
3. Note: per the agreed audit scope, the cluster-vs-plain-rate distinction is acceptable if both map to the same pragmatic bin. Flag only cases where collapse changes the category.

**Output:** `audit/gan/G6_cluster_handling.csv` — annotated with pragmatic category equivalence check.

#### G7: Contradictory letter audit (spot review, n=500)

For each record in the sample, check `reference[1]` (evidence) and where available the clinic date/letter content for:

1. Mutually contradictory frequency statements (e.g., "daily seizures" and "no further seizures since last visit" in the same letter).
2. Non-epileptic events counted as seizures.
3. Historical frequency reported as current.
4. Ambiguous "this year" or "since last visit" without date context.

Flag each with a severity: `irresolvable` (no reading of the letter produces a defensible label), `annotator-dependent` (reasonable alternative exists), `acceptable` (letter is consistent and label is supported).

**Output:** `audit/gan/G7_letter_contradictions.csv`

#### G8: Encoding and synthetic artefacts (programmatic, n=1,500)

Check the `clinic_date` / letter text field for:

1. UTF-8 double-encoding artefacts: `Ã`, `ï¿½`, `â€`, `Â·`.
2. Pronoun inconsistency (same letter switches gender).
3. Structural artefacts: "None Epilepsy", incomplete sentences, obvious template fill errors.

Quantify artefact rate across the full 1,500-record dataset.

**Output:** `audit/gan/G8_artefacts.csv`

---

## Part 3: Audit Implementation Plan

### Implementation order

```
Phase A (programmatic, can run unattended)
  ExECT: E1, E2, E3, E4, E6, E7, E8
  Gan:   G1, G2, G3, G4, G8

Phase B (programmatic with manual review of flagged cases)
  ExECT: E5
  Gan:   G5, G6, G7
```

### Script architecture

Write a single audit script per dataset: `src/audit_exect.py` and `src/audit_gan.py`. Each script:

1. Reads the raw data.
2. Runs all programmatic checks.
3. Writes per-check CSV outputs to `audit/exect/` and `audit/gan/`.
4. Writes a summary JSON to `audit/{dataset}/summary.json` containing:
   - Total annotation / record count.
   - Per-check error counts and rates.
   - Top-10 most frequent error patterns.
   - Estimated evaluation impact (FN rate uplift per metric).
5. Writes a `audit/{dataset}/manual_review_sample.csv` — the subset of flagged records for human review, ordered by severity.

### ExECT script: `src/audit_exect.py`

Key inputs:
- `data/ExECT 2 (2025)/Gold1-200_corrected_spelling/` — `.ann` and `.txt` files.
- `data/ExECT 2 (2025)/MarkupOutput_200_SyntheticEpilepsyLetters/` — CSV files.
- Optionally: `normalization.py` for canonical drug name lookups.

Key outputs: all `audit/exect/E{n}_*.csv` files, `audit/exect/summary.json`.

#### Core parser logic

```python
def parse_ann_file(path: Path) -> list[AnnAnnotation]:
    """Parse brat .ann format into structured annotations."""

def check_span_integrity(ann: AnnAnnotation, source_text: str) -> SpanCheck:
    """Compare ann span [start:end] against source_text. Return issue type."""

def detect_conflicts(anns: list[AnnAnnotation]) -> list[Conflict]:
    """Find overlapping annotations with contradictory numeric attributes."""

def classify_cuiphrase(phrase: str) -> str:
    """Return: specific | generic | malformed | missing."""

def check_medication_attributes(ann: AnnAnnotation) -> MedCheck:
    """Verify DrugName, DrugDose, DoseUnit, Frequency presence and consistency."""

def check_frequency_attributes(ann: AnnAnnotation) -> FreqCheck:
    """Verify count/period population and temporal scope."""
```

### Gan script: `src/audit_gan.py`

Key inputs:
- `data/Gan (2026)/synthetic_data_subset_1500.json`
- `src/gan_frequency.py` — for `label_to_monthly_frequency()`, `normalize_label()`, `pragmatic_category_from_x()`.

Key outputs: all `audit/gan/G{n}_*.csv` files, `audit/gan/summary.json`.

#### Sampling logic

```python
def stratified_sample(examples: list[GanExample], n: int = 500, seed: int = 42) -> list[GanExample]:
    """Sample n records proportionally from pragmatic category strata."""
```

---

## Part 4: Analysis and Reporting

### Quantitative report structure

The final report (`docs/30_gold_audit_results.md`) will contain:

#### ExECT section

1. **Annotation counts by entity type** — total annotations, documents with at least one annotation.
2. **Span integrity table** — error rate by type (trailing separator, truncated, mid-word, no-match) broken down by entity type. Which entity types are most affected?
3. **Conflict rate** — conflicts per 100 documents, by tier.
4. **CUIPhrase quality table** — specific/generic/malformed/missing rates by entity type.
5. **Medication attribute completeness** — % with DrugDose, DoseUnit, Frequency, and % of those where dose is consistent with span text.
6. **SeizureFrequency attribute completeness** — % with count, period, temporal scope.
7. **CSV vs .ann consistency** — % of .ann annotations represented in CSVs; % of CSV rows without matching .ann annotation.
8. **Estimated evaluation impact** — for each metric, estimated fraction of false negatives attributable to gold errors.

#### Gan section

1. **Full label distribution** — all 1,500 labels, pragmatic and purist category counts.
2. **Reference mismatch analysis** — 197 mismatches broken down by type; which direction (label more specific vs less specific than reference[0]).
3. **Seizure-free precision** — how many `multiple month/year` labels have a specific duration available in evidence.
4. **Analysis consistency** — arithmetic error rate, current-vs-historical confusion rate.
5. **Cluster handling** — rate of cluster-mention cases; rate where collapse changes pragmatic category.
6. **Letter contradiction rate** — irresolvable vs annotator-dependent vs acceptable.
7. **Artefact rate** — encoding errors, pronoun inconsistencies.

### Qualitative findings section

For each dataset: 5–10 case studies selected from the highest-severity flagged records. Each case study shows:
- The source letter text (or evidence quote for Gan).
- The gold label.
- The plausible correct or alternative label.
- The evaluation consequence (what metric is affected, and in which direction).

Include specific cases where a model prediction was more accurate than the gold, using actual run outputs from the G2/G3/G4 scored CSVs for Gan, and from any available document scores for ExECT.

### Dissertation framing section

Translate findings into dissertation-ready language:

1. **Validity statement** — what the scores measure.
2. **Limitation paragraph** — gold-quality caveats, with quantified rates.
3. **Floor and ceiling estimation** — estimated true model performance range if gold were clean.
4. **Comparison context** — how the gold quality compares to the published inter-annotator agreement (ExECT: F1 = 0.73) and Gan's own label methodology notes.

---

## Part 5: Sequencing and Scope Decisions

### What this audit will and will not do

**Will do:**
- Programmatically check every annotation in both datasets for structural and attribute-level issues.
- Quantify error rates with reproducible scripts.
- Read 500 Gan analyses and flag inconsistencies.
- Spot-review the highest-severity ExECT conflicts against source letter text.
- Produce dissertation-ready quantified caveats.

**Will not do:**
- Produce a corrected gold dataset (adjudication is out of scope for this dissertation stage).
- Rerun all evaluations against a corrected gold (though this is noted as a future direction).
- Conduct a full clinical review of every annotation by a neurologist.

### Sequencing

1. Write `src/audit_exect.py` — Phase A checks (E1, E2, E3, E4, E6, E7, E8). Run on all 200 files.
2. Write `src/audit_gan.py` — Phase A checks (G1, G2, G3, G4, G8) on full 1,500 records; Phase B checks (G5, G6, G7) on 500-record stratified sample.
3. Review output CSVs and add manual annotations to flagged rows.
4. Write `docs/30_gold_audit_results.md` from the summary JSONs and manual review notes.
5. Update `docs/28_gold_label_quality_analysis.md` with the full-dataset numbers, replacing the sample-based estimates.

---

## Appendix: Known Pre-Audit Findings

From the 20-document ExECT sample and 50-document Gan sample (full details in `docs/28_gold_label_quality_analysis.md`):

| Finding | Sample estimate | Status |
|---------|----------------|--------|
| ExECT span boundary artefacts | ~23% of 218 annotations | To be confirmed at n=2,000+ |
| ExECT medication dose conflicts | ~2 cases / 20 docs (10%) | To be confirmed at n=200 |
| ExECT CUIPhrase under-specification | ~15% of annotations | To be confirmed |
| Gan reference mismatch | 4/50 (8%) sample → 197/1,500 (13.1%) full dataset | **Confirmed at full scale** |
| Gan seizure-free imprecision | ~12% of 50-sample | To be quantified |
| Gan over-inferred time windows | ~8% of 50-sample | To be quantified |
| Gan encoding artefacts | Present, not quantified | To be quantified at n=1,500 |

---

*Next step: implement `src/audit_exect.py` and `src/audit_gan.py` following this plan.*
