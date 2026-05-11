# G3 Deep Investigation: Seizure-Free Precision in the Gan Gold Labels

**Date:** 2026-05-10  
**Method:** Manual reading of all 132 G3 cases with full analysis and evidence text.  
**Script:** `src/g3_classify.py`

---

## The Question

The G3 audit found that 126/132 (95.5%) of `"seizure free for multiple month/year"` labels had a specific numeric duration present in the evidence or analysis text. The qualitative analysis in `docs/31_gold_qualitative_analysis.md` suggested this was substantially inflated by the annotation rules themselves using "6 months" as a threshold phrase. This investigation reads every one of the 132 cases and classifies each precisely.

---

## Classification Scheme

| Code | Description |
|------|-------------|
| **A** | Threshold-only / label correct — any duration found refers to the "6-month criterion for seizure-free status" in the annotation rules, not a measured period. Label is appropriate. |
| **B** | Genuine precision opportunity — the evidence or analysis contains a specific measurable duration that *should* have been used in the label. |
| **P** | Sub-threshold problem — the analysis explicitly identifies a period of **<6 months**, yet the label is still "seizure free for multiple month". The annotator's own rules prohibit this. |
| **D** | Genuinely vague — no duration is discernible; "multiple month/year" is the correct label. |
| **C** | Ambiguous / borderline. |

---

## Results

| Category | Count | Rate |
|----------|------:|-----:|
| **A** — Threshold-only, label correct | 67 | 50.8% |
| **B** — Genuine precision opportunity | 21 | 15.9% |
| **P** — Sub-threshold, label violates annotator's own rules | 36 | 27.3% |
| **D** — Genuinely vague, label correct | 6 | 4.5% |
| **C** — Ambiguous | 2 | 1.5% |
| **Total** | 132 | 100% |

---

## Category A: Threshold-Only — 67 cases (50.8%)

The "6 months" or other duration found in the text is part of the annotation rule invocation, not a description of the actual seizure-free period. Almost every analysis for a seizure-free case contains language of the form:

> *"To classify as seizure free per the rules, at least 6 months of seizure freedom is required. We cannot confirm this duration, therefore the label is seizure free for multiple month."*

The "6 month" that the G3 regex detected is this rule threshold, not the measured duration. The label in these 67 cases is correct.

Representative examples:
- **GAN8188**: "There is no explicit date of the last clinic assessment provided. Without that date, we cannot confirm a seizure-free duration of at least 6 months." → `"seizure free for multiple month"` ✓
- **GAN4967**: "seizure diary shows no definite events for many months" — no specific count. → ✓
- **GAN7834**: "no further seizure episodes since the last appointment" — no date of last appointment. → ✓

The majority of cases in this category follow a clinic-letter convention where the letter says "no seizures since last review" without stating the date of the review. The annotation rules say you cannot assign a specific duration without an explicit date, so "multiple month" is correct.

---

## Category B: Genuine Precision Opportunities — 21 cases (15.9%)

These are cases where the analysis computes or the letter explicitly states a specific duration that was available to use but was replaced with "multiple month/year".

### B cases in full:

| Document | Duration available | Label given | What it should be |
|----------|-------------------|-------------|-------------------|
| GAN5082 | "past six months" explicit | multiple month | `seizure free for 6 month` |
| GAN7721 | May to Oct 2025 = 5 months | multiple month | `seizure free for 5 month` |
| GAN4951 | Feb to Oct 2025 = 8 months | multiple month | `seizure free for 8 month` |
| GAN5379 | last epileptic event ~6 months ago | multiple month | `seizure free for 6 month` |
| GAN13349 | "in the past 12 months, no events" | multiple year | `seizure free for 1 year` |
| GAN5210 | "no episodes for over three years" | multiple year | `seizure free for multiple year` ✓ (already correct) |
| GAN8736 | "over 18 months" explicit | **multiple month** | `seizure free for multiple year` |
| GAN8180 | April to October 2025 = ~6 months | multiple month | `seizure free for 6 month` |
| GAN5221 | since early 2024 to Oct 2025 = 18+ months | **multiple month** | `seizure free for multiple year` |
| GAN8222 | last seizure 9 months ago | multiple month | `seizure free for 9 month` |
| GAN8346 | late Feb to Oct 2025 = ~7-8 months | multiple month | `seizure free for 8 month` |
| GAN8858 | July 2024 to Oct 2025 = 15 months | **multiple month** | `seizure free for multiple year` |
| GAN8805 | "past six months, device analytics" explicit | multiple month | `seizure free for 6 month` |
| GAN8577 | 09 March to Sept 2025 = ~6 months | multiple month | `seizure free for 6 month` |
| GAN9190 | late Feb to Oct 2025 = ~7-8 months | multiple month | `seizure free for 8 month` |
| GAN4831 | early April to Oct 2025 = ~6 months | multiple month | `seizure free for 6 month` |
| GAN8854 | "8-month seizure calendar" explicit | multiple month | `seizure free for 8 month` |
| GAN7738 | "last appointment six months ago" explicit | multiple month | `seizure free for 6 month` |
| GAN9250 | since January 2025 to Oct = ~9 months | multiple month | `seizure free for 9 month` |
| GAN8006 | "no blackouts over the past six months" explicit | multiple month | `seizure free for 6 month` |
| GAN9588 | Feb 2025 to Oct 2025 = ~7 months | multiple month | `seizure free for 7 month` |

**Notable sub-pattern:** 3 cases (GAN8736, GAN5221, GAN8858) are labelled as "seizure free for **multiple month**" when the actual period is 15–18+ months — these should be "seizure free for **multiple year**". The annotator mislabelled the period-unit as well as failing to be specific.

**Evaluation impact of B cases:** These 21 cases are where our models are directly penalised for being more precise than the gold. GAN7738 is the clearest case — the letter says "since the last appointment six months ago" and the gold label is "multiple month". A model that reads this and outputs "seizure free for 6 month" is correct, but scores 0 on exact accuracy. At pragmatic level, both map to NS, so pragmatic F1 is unaffected. But B cases explain a real fraction of the exact-accuracy gap.

---

## Category P: Sub-Threshold Labelling — 36 cases (27.3%)

**This is the most important finding in the G3 investigation.**

The Gan annotation contract states explicitly that `"seizure free for N month"` should only be used when the patient has been seizure-free for **at least 6 months**. If the seizure-free period is shorter, the label should not be "seizure free" — it should be the most recent pre-seizure-free rate, or "unknown" if no rate can be determined.

In 36 cases, the analysis explicitly identifies a seizure-free period of <6 months, and the label is still `"seizure free for multiple month"`. The annotator's own rules prohibit this.

### P cases — period lengths:

| Period documented | Count |
|------------------|------:|
| ~1 month or less | 3 |
| ~6–10 weeks | 4 |
| 2 months | 5 |
| 3 months | 12 |
| 4 months | 7 |
| 4–5 months | 5 |
| 5 months (borderline) | 0 |
| **Total** | **36** |

Selected examples:
- **GAN7816**: Analysis says "no observed or reported events since the start of last month." One month of seizure freedom → label is "seizure free for multiple month". 
- **GAN8791**: "clear improvement over the last six weeks." Six weeks → label is "seizure free for multiple month".
- **GAN8790**: Letter provides wearable data showing "no events over the past 8 weeks." Eight weeks → label is "seizure free for multiple month".
- **GAN8813**: "over the past 90 days (three months), zero seizure activity." Three months explicit → label is "seizure free for multiple month".
- **GAN8286**: Analysis computes "No clinical seizure events during the last three months" → label is "seizure free for multiple month".
- **GAN5136**: "The interval specified is since the last clinic review three months ago." Three months → label is "seizure free for multiple month".

### Why is this happening?

Reading the analyses of P cases, the pattern becomes clear. The analyses follow a template:

1. Identify the most recent seizure-free period.
2. Check if it is ≥6 months.
3. If not ≥6 months, note "we cannot label as seizure free."
4. **Then label as "seizure free for multiple month" anyway.**

Step 4 contradicts step 3. The analyses often say something like: *"This is fewer than 6 months, so we cannot confirm seizure-free status per the rules. However, the patient currently has no seizures and the label seizure free for multiple month is used to capture current seizure-free status."*

This appears to be a deliberate annotation policy decision that overrides the written rules: **annotators chose to use the seizure-free label whenever the patient is currently seizure-free, regardless of the 6-month threshold.** The written rule ("≥6 months required") was not enforced in practice.

### What the correct label should be

For most P cases, the correct label under a strict reading of the Gan rules would be either:
1. The most recent pre-seizure-free rate (if the letter contains one)
2. "unknown" (if no rate is recoverable)

But if the de facto rule is "currently seizure-free at time of clinic → label as seizure free for multiple month regardless of duration", then the P labels are internally consistent with each other — just inconsistent with the written rules.

---

## Revised G3 Summary

The initial G3 number (95.5%) was severely misleading. The corrected picture:

| Finding | Rate |
|---------|------|
| **Label is correct and appropriate** (A + D) | 55.3% |
| **Genuine precision opportunity** (B) — model penalised for being more specific | 15.9% |
| **Sub-threshold labelling violation** (P) — annotator's own threshold not applied | 27.3% |
| **Ambiguous** (C) | 1.5% |

The dominant finding is not "labels should be more specific" (15.9%). It is "the seizure-free label is applied to periods well below the annotator's own stated threshold" (27.3%).

---

## Implications

### For evaluation

**Exact accuracy:** B cases explain some of the exact-accuracy gap. Specifically, when models correctly output a specific duration (e.g., `"seizure free for 6 month"`) against a gold label of `"multiple month"`, they score 0 — despite being more correct. This accounts for roughly 21/1,500 = 1.4% of all records, which is meaningful but not large.

**Pragmatic accuracy:** Neither B nor P cases materially affect pragmatic F1, because all "seizure free for X" variants map to NS regardless of the specific number or whether the duration is above or below 6 months.

**The P cases introduce a different problem:** 36 records (2.4% of all 1,500) are labelled as NS when, under the strict annotation rules, they should not be — the patient had only 2–5 months of seizure freedom. If a model correctly identifies the recent seizure history (e.g., "the patient had 3 per month until October, then stopped") and outputs a rate label, it will be scored wrong against a gold NS label. This is a small but real source of unfair scoring in the opposite direction from B: not "model too precise for gold" but "gold too generous for model's correct rate".

### For the dissertation

The G3 finding should be rewritten entirely. The correct framing is:

> "A deep investigation of all 132 Gan gold labels with 'seizure free for multiple month/year' — read individually with full analysis and evidence text — reveals three distinct sub-populations. The majority (51%) are correctly labelled as 'multiple' because the specific duration is genuinely unknown from the letter; the 'six months' found by the automated search was the annotation rule threshold, not a measured period. A genuine precision opportunity exists in 16% of cases, where a specific duration was present in the letter or calculable from dates but was replaced with the vague form — these cases penalise models for being more specific than the gold. The most unexpected finding is that 27% of cases apply the seizure-free label to periods explicitly identified in the analysis as shorter than the annotator's own stated 6-month threshold, suggesting the threshold was not enforced in practice. Neither of these two error classes materially affects pragmatic F1 (all map to the same NS category), but they introduce real noise at the exact-label accuracy level and complicate any interpretation of seizure-free duration precision."

### For the annotation scheme

The 6-month threshold is not uniformly applied. Either:
- The threshold should be removed and replaced with "any duration of current seizure freedom", or
- The ~36 sub-threshold cases should be relabelled to the most recent pre-cessation rate

Without adjudication, the Gan gold contains a mixed seizure-free labelling convention: some "seizure free" labels reflect ≥6 months of freedom, others reflect as little as 4–6 weeks. This inconsistency means that "seizure free for multiple month" carries ambiguous clinical information — it could mean 6 months, or it could mean 6 weeks.

---

## The 6 D Cases (Genuinely Correct "Multiple")

For completeness, the 6 cases where no duration was found and "multiple" is entirely appropriate:
- **GAN7708**: "seizure occurrences have not been happening" since adopting ketogenic diet "for several months" — no specific date
- **GAN13485**: "not reported seizures for over several years" — no year count
- **GAN9147**: Patient does not have epilepsy (vestibular migraine); no epileptic seizure-free period to measure
- **GAN13584**: Seizure-free since mid-adolescence — no specific age or year
- **GAN9238**: "No definite seizures during this period" — period duration unspecified
- **GAN7894**: "Entirely seizure-free in adult life" — no adult lifespan given

These are the purest "multiple" labels — genuinely vague by letter content, not by annotator convention.
