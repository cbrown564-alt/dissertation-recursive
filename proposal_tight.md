Research proposal: reliable event-first extraction from epilepsy clinic letters

Working title

Evidence-Grounded Event-First Extraction from Epilepsy Clinic Letters: A Reliability Evaluation of Training-Free LLM Pipelines

---

1. Summary

This dissertation will investigate how to build a reliable, training-free clinical information extraction pipeline for epilepsy clinic letters. The project will focus on a narrow but clinically important problem: whether decomposing letters into evidence-grounded clinical events before deriving final structured fields improves reliability compared with direct structured extraction.

The core task is to read an epilepsy clinic letter and extract a small set of high-value fields:

- current anti-seizure medication
- previous anti-seizure medication
- medication dose and status where stated
- seizure frequency
- seizure type
- EEG status/result
- MRI status/result
- epilepsy diagnosis or epilepsy type where stated

The central research problem is not simply whether a large language model can produce plausible structured data. The problem is whether an extraction system can produce outputs that are accurate, evidence-supported, temporally correct, conservative when information is absent, and reproducible under realistic cost and model constraints.

The dissertation will compare direct field extraction against an event-first pipeline. In the direct approach, the model extracts final fields from the whole letter. In the event-first approach, the model first identifies temporally qualified clinical events, attaches exact evidence spans, and then derives final structured fields from those events. The hypothesis is that event-first extraction will be most useful for fields where temporality matters, especially seizure frequency, medication status, and investigation status.

JSON versus YAML and open versus closed models will be included as controlled secondary analyses, not as the main contribution. Multi-agent systems, self-consistency, and autoresearch loops will be treated as future work unless time permits after the main evaluation is complete.

---

2. Background and rationale

Epilepsy clinic letters contain information that is clinically and scientifically valuable but difficult to use at scale. Letters often describe seizure semiology, seizure frequency, anti-seizure medication history, investigations, diagnostic uncertainty, and management plans in free text. This information may be missing or under-specified in structured clinical systems, limiting audit, research, and clinical decision support.

Previous epilepsy NLP work, including ExECT and ExECTv2, has shown that structured epilepsy information can be extracted from clinic letters. These systems provide an important baseline and demonstrate the value of transforming free-text epilepsy records into structured data. However, rule-based or traditional NLP pipelines can require substantial domain-specific engineering, and may struggle with variation in wording, temporal qualification, and local documentation style.

Large language models create a new opportunity for training-free or minimal-training extraction. A prompted LLM can often identify clinically relevant information without task-specific model training. This is attractive in clinical settings because labelled data are scarce, governance constraints are substantial, and open or local models may be preferred for privacy-preserving deployment.

However, naive LLM extraction is not reliable enough for clinical information extraction. A valid-looking JSON object can still contain unsupported claims, temporal errors, overconfident guesses, or values copied from the wrong part of the letter. In epilepsy letters, this is especially risky because the same letter may mention current medications, previous medications, planned changes, family history, historical seizure frequencies, current seizure freedom, and uncertain diagnoses.

This project therefore frames the dissertation as a reliability study. The aim is to evaluate whether a structured, evidence-grounded, event-first pipeline can reduce the specific failure modes that matter most in epilepsy clinic-letter extraction.

---

3. Core aim

The main aim is to determine whether event-first, evidence-grounded extraction improves the reliability of structured information extraction from epilepsy clinic letters compared with direct structured extraction.

The project will focus on reliability across five dimensions:

- field-level accuracy
- temporal correctness
- evidence support
- abstention when information is absent
- robustness to realistic letter variation

The dissertation will also report parseability, schema validity, cost, latency, and model-family differences, but these are secondary to the main event-first reliability question.

---

4. Research questions

RQ1 - Event-first extraction

Does extracting temporally qualified clinical events before deriving final fields improve field-level accuracy and temporal correctness compared with direct structured extraction?

RQ2 - Evidence grounding

Does requiring exact evidence spans reduce unsupported extractions, and what trade-off does this create between precision, recall, and abstention?

RQ3 - Reliability under perturbation

Does event-first extraction improve robustness under realistic perturbations such as reordered sections, missing headings, historical medication mentions, planned medication changes, family-history traps, negation, and temporal contrast?

RQ4 - Structured output format as a secondary factor

Does model-facing output format, specifically JSON versus YAML-to-JSON, affect parseability, schema validity, repair rate, and extraction accuracy?

RQ5 - Model-family comparison as a secondary factor

How do selected open/local and closed/frontier models compare on the same extraction pipelines under controlled call, token, cost, and latency constraints?

---

5. Hypothesis

The main hypothesis is:

Event-first, evidence-grounded extraction will improve reliability for temporally complex epilepsy fields compared with direct structured extraction, especially for seizure frequency, medication status, and investigation status. The improvement should be visible in temporal accuracy, evidence support, and robustness, even if the pipeline has higher latency or token cost.

Secondary hypotheses are:

- Requiring evidence spans will reduce unsupported extractions but may reduce recall when evidence is implicit or distributed across the letter.
- JSON will remain the preferred canonical internal and scoring format, but YAML-to-JSON may improve generation robustness for some smaller or open models.
- Closed/frontier models will likely perform best overall, but open/local models may become competitive on narrower event extraction tasks when schema validation and evidence checks are strict.

---

6. Proposed system design

The system will be modular so that each component can be evaluated and ablated.

Input epilepsy clinic letter

Preprocessor

- normalize whitespace
- split into sentences or spans
- assign sentence IDs
- preserve character offsets

Direct extraction baseline

- read the whole letter
- output final structured fields directly
- include missingness status and evidence where required

Event-first pipeline

- identify section context where available
- extract clinical events with temporality
- attach exact evidence spans
- derive final fields deterministically or with a constrained aggregation step
- output canonical JSON

Evaluation harness

- parse outputs
- validate schema
- check evidence spans against source text
- score fields against gold labels
- log cost, latency, token use, and repair events

The key design choice is to separate intermediate clinical events from final patient-level fields.

Example intermediate events:

```yaml
events:
  - id: e1
    category: medication
    medication: lamotrigine
    dose: 100 mg twice daily
    status: current
    temporality: current
    evidence: "She remains on lamotrigine 100 mg twice daily."

  - id: e2
    category: seizure_frequency
    value: seizure-free
    temporal_scope: past six months
    temporality: current
    evidence: "She has been seizure-free for the past six months."

  - id: e3
    category: medication
    medication: levetiracetam
    status: previous
    reason_stopped: mood changes
    temporality: historical
    evidence: "Levetiracetam was stopped because of mood changes."
```

Example final fields:

```json
{
  "current_anti_seizure_medications": [
    {
      "name": "lamotrigine",
      "dose": "100 mg twice daily",
      "evidence_event_id": "e1"
    }
  ],
  "previous_anti_seizure_medications": [
    {
      "name": "levetiracetam",
      "reason_stopped": "mood changes",
      "evidence_event_id": "e3"
    }
  ],
  "current_seizure_frequency": {
    "value": "seizure-free",
    "temporal_scope": "past six months",
    "evidence_event_id": "e2"
  }
}
```

This design makes temporal ambiguity explicit. The system is not simply asked "what is the seizure frequency?" It is asked to identify all relevant seizure-frequency events and then select the current clinically relevant value.

---

7. Experimental design

Phase 1 - Dataset, schema, and scoring

The first phase will define the canonical extraction schema, dataset splits, and scoring code before prompt optimization begins. The initial dataset will be the public synthetic annotated epilepsy clinic-letter corpus. If de-identified real clinic letters become available through appropriate governance, they will be used only as an external validation set.

The schema will be deliberately narrow. It will prioritise fields that are both clinically useful and likely to expose temporal extraction errors:

- current anti-seizure medication
- previous anti-seizure medication
- medication dose where stated
- seizure frequency and temporal scope
- seizure type
- EEG status/result
- MRI status/result
- epilepsy diagnosis/type

Each extracted field will include:

- value
- status or temporality where relevant
- missingness status
- evidence quote
- sentence ID or character offsets where feasible
- confidence, if produced by the model

Phase 2 - Direct extraction baselines

The project will first build strong direct baselines:

S1 - Direct JSON extraction

The model reads the full letter and emits canonical JSON directly.

S2 - Direct JSON extraction with evidence

The model emits final fields plus exact evidence quotes.

S3 - Direct YAML-to-JSON extraction with evidence

The model emits YAML, which is parsed and converted into the same canonical JSON schema.

These baselines establish whether evidence and model-facing format matter before adding event-first decomposition.

Phase 3 - Event-first extraction

The main experimental system will then be built:

E1 - Event extraction only

The model extracts all relevant medication, seizure, investigation, and diagnosis events with temporality and evidence.

E2 - Event-first extraction plus deterministic aggregation

A rule-based aggregator derives final fields from event objects where possible. For example, current medications are selected from events labelled current; historical medications are selected from events labelled previous; investigation status is derived from requested, completed, normal, abnormal, or unknown events.

E3 - Event-first extraction plus constrained aggregation

Where deterministic rules are insufficient, a constrained model call derives final fields from the event list rather than from the whole original letter.

The main comparison will be S2 versus E2/E3, because both conditions require evidence but differ in whether the model extracts final fields directly or works through intermediate events.

Phase 4 - Secondary model and format comparison

After the primary pipeline is working, the same conditions will be run across a small, controlled model set:

- one strong closed/frontier model
- one cheaper closed model
- one open/local medium model
- optionally one smaller open/local model

The project will avoid a broad model leaderboard. The goal is to understand whether the event-first reliability effect persists across model families and whether model-facing JSON or YAML-to-JSON changes parseability or accuracy.

Phase 5 - Robustness tests

The final phase will apply systematic perturbations to the letters. These will be generated from the source letters while preserving the intended gold labels where possible.

Perturbations will include:

- reordered sections
- removed headings
- bullet lists converted to prose
- added historical medication mentions
- added planned medication changes
- added family-history traps
- added negation
- temporal contrast, such as "previously weekly, now seizure-free"
- investigation ambiguity, such as "MRI requested" versus "MRI normal"

These tests directly evaluate the claim that event-first extraction improves reliability under temporally complex conditions.

---

8. Evaluation plan

The evaluation will separate extraction accuracy from reliability properties.

Field-level extraction metrics:

- medication name precision, recall, and F1
- medication status accuracy
- dose exact and relaxed match
- seizure type F1
- seizure-frequency normalized-value accuracy
- seizure-frequency temporal accuracy
- EEG and MRI status/result F1
- diagnosis/type exact or partial match
- missingness accuracy

Evidence metrics:

- percentage of extracted fields with an exact source quote
- quote validity, defined as whether the quote appears in the source text
- evidence overlap with annotated span where available
- unsupported extraction rate

Format and schema metrics:

- parse success rate
- repair rate
- repair success rate
- schema validity
- type correctness
- output token cost

Reliability metrics:

- abstention quality for not-stated fields
- robustness under perturbation
- stability across repeated runs where budget allows
- cost per correctly supported field
- latency per letter

Statistical analysis will compare paired outputs on the same letters wherever possible. The primary analysis will compare direct evidence-based extraction against event-first evidence-based extraction on temporally complex fields.

---

9. Scope control

The minimum viable dissertation will include:

1. A canonical schema and scoring harness.
2. Direct JSON extraction baseline.
3. Direct evidence-grounded extraction baseline.
4. Event-first extraction with evidence.
5. Deterministic or constrained aggregation from events to final fields.
6. A focused comparison on seizure frequency, medication status, investigation status, seizure type, and diagnosis/type.
7. A small open-versus-closed model comparison.
8. A limited JSON-versus-YAML-to-JSON format comparison.
9. Robustness tests targeting temporal ambiguity.

The following are explicitly out of core scope:

- broad multi-agent architectures
- unconstrained autonomous agents
- self-consistency across many repeated samples
- fine-tuning
- autoresearch loops
- deployment into a live clinical environment
- claims of clinical safety without real-world validation

These may be discussed as extensions, but the dissertation will not depend on them.

---

10. Expected contributions

Contribution 1 - A reproducible evaluation harness

The project will produce a modular harness for evaluating training-free structured extraction from epilepsy clinic letters, including schema validation, evidence checking, scoring, and cost/latency logging.

Contribution 2 - An event-first extraction architecture

The project will evaluate whether extracting temporally qualified events before final fields improves reliability for epilepsy-letter information extraction.

Contribution 3 - Evidence-grounded extraction analysis

The dissertation will quantify how exact evidence requirements affect unsupported extraction, abstention, precision, and recall.

Contribution 4 - Reliability-focused robustness tests

The project will include targeted perturbation tests for the clinical failure modes most relevant to epilepsy letters, especially temporal contrast, historical mentions, planned changes, negation, and family-history traps.

Contribution 5 - Practical model and format guidance

The project will provide bounded empirical guidance on JSON versus YAML-to-JSON and open/local versus closed/frontier models for this task.

---

11. Risks and mitigations

Risk: Synthetic data may not reflect real clinical variation.

Mitigation: Treat the synthetic dataset as the main reproducible benchmark. Use perturbation tests and, if available, real de-identified letters only as external validation.

Risk: Event-first extraction may cost more without improving accuracy.

Mitigation: Report cost-normalised metrics, including cost per correctly supported field, and compare systems under fixed call or token budgets.

Risk: Evidence quotes may be copied correctly but attached to the wrong interpretation.

Mitigation: Score evidence validity separately from field correctness and temporal correctness.

Risk: YAML may introduce type coercion or ambiguous parsing.

Mitigation: Parse YAML with strict settings, convert immediately to typed canonical JSON, and score only the canonical representation.

Risk: Model comparisons may become too broad.

Mitigation: Limit the model set to two closed models and one or two open/local models.

Risk: Prompt iteration may overfit the development set.

Mitigation: Lock dataset splits, schema, and scoring code before major prompt optimization. Keep the final test set untouched until the final evaluation.

---

12. Proposed chapter structure

Chapter 1 - Introduction

- clinical motivation
- epilepsy letters as free-text evidence sources
- reliability problem
- core research question

Chapter 2 - Literature Review

- epilepsy information extraction
- ExECT and ExECTv2
- LLM-based clinical information extraction
- evidence-grounded extraction and faithfulness
- temporal information extraction in clinical text
- structured outputs and schema validation
- open/local versus closed/frontier model considerations

Chapter 3 - Data and Schema

- synthetic epilepsy-letter dataset
- target fields
- annotation assumptions
- canonical JSON schema
- evidence-span representation
- dataset splits

Chapter 4 - Methods

- direct extraction baselines
- event-first extraction pipeline
- evidence binding
- aggregation from events to final fields
- model and format conditions
- implementation details

Chapter 5 - Evaluation

- extraction metrics
- evidence metrics
- temporal correctness metrics
- robustness tests
- cost and latency analysis
- statistical comparison

Chapter 6 - Results

- direct baseline results
- event-first results
- field-specific error analysis
- robustness results
- model and format secondary analyses

Chapter 7 - Discussion

- when event-first extraction helps
- where evidence grounding succeeds or fails
- clinical deployment implications
- limitations of synthetic data
- implications for open/local models

Chapter 8 - Conclusion

- summary of findings
- practical recommendations
- future work

---

13. Literature review plan

The next stage will conduct a full literature review to support and refine this proposal. The review should cover five strands:

1. Epilepsy information extraction from clinic letters and electronic health records.
2. Clinical NLP methods for temporality, negation, uncertainty, and evidence spans.
3. LLM-based clinical information extraction and structured output reliability.
4. Evidence-grounded or citation-grounded extraction systems.
5. Open/local versus closed/frontier model evaluation in clinical or privacy-sensitive settings.

The literature review should answer four practical questions before implementation begins:

- What fields and definitions should be aligned with prior epilepsy NLP work?
- What should count as a correct seizure-frequency, medication-status, or investigation-status extraction?
- What evidence-span and temporal-scoping metrics are defensible?
- What model and structured-output comparisons are worth including without widening the dissertation too far?

---

14. Final concise proposal statement

This dissertation will evaluate whether event-first, evidence-grounded LLM extraction improves the reliability of structured information extraction from epilepsy clinic letters. Rather than asking a model to directly produce final patient-level fields, the proposed system first extracts temporally qualified clinical events with exact evidence spans, then derives final structured fields through deterministic or constrained aggregation. The project will compare this approach against direct structured extraction baselines using a public synthetic epilepsy-letter dataset, focused clinical fields, robustness tests, and cost-aware reliability metrics. JSON versus YAML-to-JSON and open/local versus closed/frontier models will be evaluated as secondary factors. The expected contribution is a reproducible evaluation harness and an empirical account of when event-first evidence grounding improves clinical extraction reliability.
