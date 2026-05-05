Research proposal: reliable training-free extraction from epilepsy clinic letters using recursive, evidence-grounded agents

Working title

Reliability Engineering for Training-Free Clinical Information Extraction from Epilepsy Clinic Letters: Recursive Agents, Structured Outputs, and Open-vs-Closed Model Evaluation

⸻

1. Summary

This dissertation will develop and evaluate a training-free or minimal-training extraction system that reads epilepsy clinic letters and outputs structured clinical fields, including anti-seizure medications, seizure type, seizure frequency, investigations, epilepsy type, and epilepsy syndrome.

The central research problem is reliability, not simply extraction performance. The project will compare single-prompt extraction against increasingly structured approaches: evidence-grounded extraction, recursive section/event extraction, multi-agent verification, and self-consistency. A key early experimental variable will be structured output format, comparing JSON vs YAML across open and closed models.

This is clinically motivated because epilepsy-relevant information is often locked in free-text letters, and previous work such as ExECT has shown the value of extracting structured epilepsy information from unstructured clinic letters.  ￼ The project is also feasible because there is now a public set of 200 synthetic annotated epilepsy clinic letters with annotation guidelines, specifically created for NLP research in this domain.  ￼

⸻

2. Background and rationale

Epilepsy clinic letters contain clinically valuable but hard-to-use information: medication history, current treatment, seizure semiology, seizure frequency, investigation results, diagnostic uncertainty, and treatment plans. Prior epilepsy NLP work has targeted this problem through rule-based and traditional NLP pipelines, including ExECT, which aimed to extract detailed epilepsy information from clinic letters to enrich routinely collected health data.  ￼

Recent LLM-based extraction creates a new opportunity: rather than training a bespoke model from scratch, one can build a training-free or minimal-training extraction pipeline using prompting, structured output validation, evidence spans, and verification agents. This is attractive in clinical settings because labelled data are scarce, governance is restrictive, and local/open models may be preferred for privacy and deployment reasons.

However, naïve LLM extraction is risky. Clinical extraction systems need more than valid-looking answers. They need:

* support from the source text,
* correct handling of temporal context,
* conservative abstention when evidence is absent,
* robustness to noisy or inconsistent letters,
* reproducible output formats,
* measurable error profiles,
* and acceptable cost/latency.

This project therefore frames the dissertation as a reliability-engineering study.

⸻

3. Core research aim

The main aim is to determine whether recursive, evidence-grounded, multi-agent extraction improves the reliability of structured epilepsy-letter extraction compared with strong single-prompt baselines, under controlled budget constraints.

A secondary aim is to evaluate whether YAML or JSON is more reliable as the model-facing structured output format, especially when comparing open/local models against closed/frontier models.

⸻

4. Research questions

RQ1 — Agentic reliability

Does a multi-agent extraction pipeline improve field-level accuracy, evidence support, abstention quality, and robustness compared with single-prompt extraction under the same token or call budget?

RQ2 — Recursive extraction

Does extracting intermediate section maps and clinical event timelines before final field extraction improve reliability for temporally complex epilepsy fields such as seizure frequency, medication status, and investigation status?

RQ3 — Evidence grounding

Does requiring explicit evidence quotes reduce unsupported or hallucinated extractions, and what is the trade-off between improved precision and reduced recall?

RQ4 — Structured output format

Does the model-facing output format, specifically JSON vs YAML, affect parseability, schema validity, field accuracy, and repair rate across different model families?

RQ5 — Open vs closed models

How do open/local models compare with closed/frontier models for this clinical extraction task, especially when constrained by privacy, cost, and reproducibility considerations?

RQ6 — Autoresearch extension

Can a bounded autoresearch loop accelerate the development of extraction prompts, validation rules, and pipeline variants without compromising experimental validity?

⸻

5. Key hypothesis

The main hypothesis is:

Recursive, evidence-grounded extraction will improve reliability for temporally complex fields, while structured validation and verification will reduce unsupported answers. YAML may improve generation robustness for some small/open models, but canonical JSON will remain preferable for validation, scoring, and downstream storage.

This hypothesis is deliberately balanced. Mattingly’s recent large-scale name-parsing study reports that switching from JSON to YAML eliminated syntax issues in their small-model historical-name parsing workflow and helped achieve 94–96% accuracy with fine-tuned Qwen models.  ￼ However, a 2025 clinical-notes study comparing JSON, YAML, and XML for small-language-model attribute-value extraction found that JSON had the highest parseability in that clinical setting.  ￼ Therefore, the proposal should treat JSON vs YAML as an empirical question, not as a settled design choice.

⸻

6. Proposed system architecture

The proposed system will be modular so that each component can be ablated and evaluated.

Input epilepsy clinic letter
        |
        v
Preprocessor
- section/sentence indexing
- character offsets
- optional de-identification check
        |
        v
Recursive Section/Timeline Agent
- segments the letter
- identifies dated or temporally qualified events
- distinguishes current, historical, planned, family-history, and uncertain statements
        |
        v
Field Extractor Agents
- medication extractor
- seizure extractor
- investigation extractor
- diagnosis/syndrome extractor
        |
        v
Evidence Binder
- attaches exact quotes
- validates that quotes appear in source text
- records sentence IDs and character offsets
        |
        v
Verification Agent
- checks evidence support
- checks contradictions
- checks missingness
- flags uncertainty
        |
        v
Aggregator
- produces final structured output
- normalises fields
- assigns confidence
- outputs canonical JSON
        |
        v
Evaluation Harness
- accuracy/F1
- parseability
- schema validity
- evidence validity
- robustness
- cost/latency

The key architectural choice is to make the system event-first rather than field-first.

Instead of directly extracting:

{
  "current_asm": "lamotrigine",
  "seizure_frequency": "monthly"
}

the recursive system first extracts intermediate events:

events:
  - id: e1
    type: medication_current
    drug: lamotrigine
    dose: 100 mg twice daily
    temporality: current
    evidence: She remains on lamotrigine 100 mg twice daily.
  - id: e2
    type: seizure_frequency
    value: seizure-free
    temporal_scope: past six months
    temporality: current
    evidence: She has been seizure-free for the past six months.
  - id: e3
    type: medication_previous
    drug: levetiracetam
    temporality: historical
    reason_stopped: mood changes
    evidence: Levetiracetam was stopped because of mood changes.

Final fields are then derived from these event objects.

This is likely to help with the hardest clinical ambiguity: distinguishing past, current, planned, and family-history information.

⸻

7. JSON vs YAML as an early experimental variable

This should be tested early because it affects the entire pipeline design.

7.1 Why test it early?

The structured output format affects:

* parse failure rate,
* schema validity,
* retry/repair burden,
* ease of prompting small models,
* evidence quote preservation,
* downstream validation,
* and human debugging.

The Mattingly post suggests YAML may be easier for small fine-tuned models in some structured extraction settings, especially when JSON syntax is brittle.  ￼ But clinical-note evidence points the other way, with JSON outperforming YAML and XML in parseability for small language models.  ￼ That tension makes this a valuable dissertation sub-study.

7.2 Proposed format conditions

Condition	Description
JSON-direct	Model emits JSON directly
YAML-direct	Model emits YAML directly
YAML-to-JSON	Model emits YAML; pipeline parses and converts to canonical JSON
JSON-constrained	Model emits JSON using structured output or constrained decoding where available
Repair-enabled JSON	Invalid JSON is repaired once
Repair-enabled YAML	Invalid YAML is repaired once

The most practical production design is likely:

Model-facing intermediate format: YAML or JSON, depending on model
Canonical internal format: typed Python/Pydantic object
Final persisted/scored format: JSON

That allows the dissertation to test YAML fairly without giving up JSON Schema, Pydantic, and downstream reproducibility.

⸻

8. Open vs closed model comparison

Clinical settings often prefer local or open models because they offer stronger control over data flow, reproducibility, deployment environment, and cost. But closed/frontier models may still perform better, especially on difficult reasoning, temporality, and verification tasks.

The comparison should therefore not simply ask “which model is best?” It should ask:

Which model gives the best reliability-cost-privacy trade-off under realistic clinical constraints?

Proposed model categories

Category	Example role in study
Closed/frontier model	Upper-bound performance baseline
Closed cheaper/mini model	Cost-sensitive API baseline
Open medium model	Likely local deployment candidate
Open small model	Privacy/cost-sensitive extraction candidate
Open small model with YAML	Tests Mattingly-style hypothesis
Hybrid open/closed	Local extraction, closed verification, if governance permits

The exact models can be chosen later based on institutional access and hardware. The proposal does not need to commit prematurely.

⸻

9. Experimental design

Phase 1 — Dataset and schema

Use the public synthetic annotated epilepsy clinic letters as the initial development and evaluation resource. These 200 synthetic letters and guidelines were created to support epilepsy NLP research and validate ExECTv2.  ￼ If de-identified real clinic letters become available, use them as an external validation set rather than making the dissertation dependent on data access.

Target fields:

Anti-seizure medications:
- current ASM
- previous ASM
- dose
- medication changes
- adverse effects
- planned changes
Seizure information:
- seizure type
- seizure frequency
- last seizure
- seizure freedom
- temporal scope
- triggers where available
Investigations:
- EEG
- MRI
- CT
- genetic testing
- blood tests
- status: completed / requested / normal / abnormal / unknown
Diagnosis:
- epilepsy type
- epilepsy syndrome
- diagnostic certainty
- differential diagnoses
Meta-fields:
- evidence quote
- sentence ID
- character offsets
- confidence
- missingness status

Phase 2 — Baseline systems

Build the simplest viable systems first.

System	Description
S0	Rule-based baseline for simple fields, e.g. medication names
S1	Single-prompt JSON extraction
S2	Single-prompt YAML extraction
S3	Single-prompt with evidence quotes
S4	Single-prompt with schema validation

This phase establishes whether format and evidence requirements matter before multi-agent complexity is introduced.

Phase 3 — Recursive extraction systems

Add increasingly structured pipelines.

System	Description
R1	Section-recursive extraction
R2	Event-recursive extraction
R3	Event-recursive extraction plus evidence binder
R4	Event-recursive extraction plus verifier
R5	Event-recursive extraction plus verifier plus aggregator

This phase tests the main recursive hypothesis.

Phase 4 — Multi-agent and self-consistency

Add role-specialised agents and repeated sampling.

System	Description
M1	Field-specific agents without verifier
M2	Field-specific agents with verifier
M3	Multi-agent with self-consistency
M4	Self-consistency only for low-confidence fields
M5	Multi-agent with contradiction search

The budget must be controlled. For example, compare systems under:

Budget A: one model call per letter
Budget B: three calls per letter
Budget C: five calls per letter
Budget D: fixed maximum token budget

This avoids the unfair conclusion that multi-agent systems are better simply because they use more inference.

Phase 5 — Autoresearch extension

A bounded autoresearch loop can be added after the harness exists.

The loop should be allowed to:

* propose prompt variants,
* propose validation rules,
* generate perturbation tests,
* run experiments on the development set,
* analyse error clusters,
* log results,
* recommend whether to keep or reject changes.

It should not be allowed to:

* change gold labels,
* change scoring metrics,
* inspect the locked test set,
* silently drop difficult examples,
* change dataset splits,
* or report final claims without human review.

Karpathy’s autoresearch repository illustrates the broader pattern: an agent modifies code, runs short experiments, checks whether the result improved, keeps or discards the change, and repeats.  ￼ For this dissertation, the same pattern can be adapted from model training to prompt, schema, and pipeline optimisation.

⸻

10. Evaluation plan

10.1 Format-level metrics

These directly address JSON vs YAML.

Metric	Definition
Parse success rate	Output can be parsed without repair
Repair rate	Output requires automated repair
Repair success rate	Invalid output becomes valid after one repair
Schema validity	Parsed output conforms to schema
Type correctness	Fields have expected types
Serialization token cost	Output length and cost by format
Human readability	Optional qualitative debugging assessment

10.2 Extraction metrics

Field type	Metrics
Medication names	precision, recall, F1
Medication status	accuracy / macro-F1
Dose	exact and relaxed match
Seizure type	label F1
Seizure frequency	normalized-value accuracy plus temporal accuracy
Investigations	F1 by investigation type and status
Epilepsy type/syndrome	exact/partial match
Missingness	accuracy of not_stated
Evidence span	exact quote match and overlap F1

10.3 Reliability metrics

Reliability dimension	Metric
Faithfulness	percentage of extracted fields supported by valid quote
Unsupported extraction	fields with no source support
Abstention quality	correct not_stated decisions
Contradiction handling	performance on seeded contradictions
Stability	agreement across repeated runs
Robustness	performance under perturbation
Calibration	confidence vs correctness
Cost	tokens, calls, local compute, API cost
Latency	time per letter

⸻

11. Robustness tests

Synthetic perturbations should be generated systematically.

Examples:

1. Reorder sections.
2. Remove headings.
3. Add OCR-like punctuation noise.
4. Convert bullet lists to prose.
5. Add historical medication mentions.
6. Add planned medication changes.
7. Add family history traps.
8. Add negation:
   “No generalized tonic-clonic seizures since 2020.”
9. Add temporal contrast:
   “Previously weekly, now seizure-free for six months.”
10. Add investigation ambiguity:
   “MRI requested” vs “MRI normal.”

These tests are especially important for evaluating whether recursive timeline extraction actually improves reliability.

⸻

12. Autoresearch design

The autoresearch loop should be framed as an optional ambitious extension, not the main dependency.

Proposed loop

1. Read latest experiment log.
2. Identify weakest field or failure mode.
3. Generate a hypothesis.
4. Propose one bounded intervention.
5. Modify prompt/configuration only.
6. Run on development set.
7. Compute pre-defined metrics.
8. Analyse errors.
9. Keep, reject, or flag for human review.
10. Append to lab notebook.

Example autoresearch iteration

Observation:
Seizure frequency recall is low.
Hypothesis:
Extracting all seizure-frequency mentions as intermediate events before selecting the current value will improve recall.
Intervention:
Add a seizure-event extraction step.
Evaluation:
Run on development split only.
Decision:
Keep if field F1 improves and unsupported extraction rate does not increase.

Deliverable

The autoresearch system should produce a structured experiment log:

experiment_id: exp_014
date: 2026-06-12
hypothesis: Event-first seizure extraction improves seizure-frequency recall.
pipeline_variant: event_recursive_yaml_v2
model: local_open_model_a
format: yaml_to_json
dataset_split: development
metrics:
  seizure_frequency_f1: 0.74
  unsupported_rate: 0.08
  parse_success: 0.99
  mean_latency_seconds: 4.2
decision: keep_for_manual_review
notes: Improved recall but introduced two temporal errors.

This would strengthen the dissertation because it shows a disciplined AI-assisted research process rather than ad hoc prompt tweaking.

⸻

13. Expected contributions

The dissertation could make six contributions.

Contribution 1 — A reproducible extraction harness

A modular pipeline for evaluating structured extraction from epilepsy clinic letters.

Contribution 2 — A recursive event-first extraction architecture

A method that extracts section structure and clinical events before final field values.

Contribution 3 — Evidence-grounded clinical extraction

A system that requires quotes, sentence IDs, and character offsets for extracted values.

Contribution 4 — JSON vs YAML empirical comparison

A controlled evaluation of structured output format across open and closed models in a clinical extraction task.

Contribution 5 — Open vs closed model reliability analysis

A practical comparison of local/open and closed/frontier models under clinical deployment constraints.

Contribution 6 — Bounded autoresearch methodology

An optional framework for using coding/research agents to propose and evaluate extraction pipeline improvements while preserving scientific validity.

⸻

14. Risks and mitigations

Risk	Mitigation
Real clinical data unavailable	Use public synthetic annotated epilepsy letters; treat real data as optional external validation
Synthetic data overfitting	Use perturbation tests and, if possible, small real validation set
Multi-agent system too complex	Build baselines first; add agents only through ablations
YAML introduces hidden type coercion	Parse with strict YAML settings; convert to typed canonical JSON
JSON has high failure rate in small models	Test YAML and repair loops early
Open models underperform	Report trade-offs honestly; use hybrid local/open architectures
Autoresearch overfits dev set	Lock test set, metrics, scoring code, and dataset splits
Verifier rubber-stamps errors	Evaluate verifier separately; include contradiction tests
Evidence quotes are paraphrased	Require exact quote matching against source text
Cost becomes excessive	Report cost-normalised metrics and selective self-consistency

⸻

15. Proposed chapter structure

Chapter 1 — Introduction

* clinical motivation
* epilepsy letters as unstructured data
* reliability problem
* research questions and contributions

Chapter 2 — Background

* epilepsy information extraction
* ExECT and prior epilepsy NLP
* LLM-based clinical extraction
* structured outputs
* JSON vs YAML
* open vs closed model considerations
* recursive and agentic workflows
* autoresearch

Chapter 3 — Data and annotation schema

* dataset description
* target fields
* schema design
* evidence-span representation
* synthetic vs real data considerations

Chapter 4 — Methods

* baseline systems
* recursive extraction pipeline
* multi-agent architecture
* output format conditions
* model selection
* validation and repair
* autoresearch loop

Chapter 5 — Evaluation

* metrics
* robustness tests
* budget constraints
* statistical comparison
* error analysis protocol

Chapter 6 — Results

* baseline comparison
* JSON vs YAML results
* open vs closed model results
* recursive extraction results
* verifier and self-consistency ablations
* autoresearch findings, if included

Chapter 7 — Discussion

* when agents help
* when recursion helps
* format trade-offs
* clinical deployment implications
* limitations

Chapter 8 — Conclusion

* summary of findings
* recommendations for reliable clinical LLM extraction
* future work

⸻

16. Recommended minimum viable dissertation

To keep the project feasible, the minimum viable version should include:

1. Dataset + schema
2. Single-prompt JSON baseline
3. Single-prompt YAML baseline
4. Evidence-required extraction
5. Recursive event-first extraction
6. Verifier agent
7. Open vs closed model comparison
8. Robustness tests
9. Final reliability analysis

The ambitious version adds:

10. Self-consistency
11. YAML-to-JSON intermediate architecture
12. Selective local/open model pipeline
13. Autoresearch loop for prompt and pipeline optimisation

⸻

17. Final proposal statement

A concise version of the proposal could be:

This dissertation will investigate how to build reliable, training-free clinical information extraction systems for epilepsy clinic letters using recursive, evidence-grounded LLM workflows. The project will compare single-prompt extraction, structured output validation, recursive event-first extraction, multi-agent verification, and self-consistency under controlled budget constraints. It will also evaluate JSON versus YAML as model-facing output formats across open/local and closed/frontier models, reflecting clinical preferences for privacy-preserving local deployment. The expected output is an end-to-end extraction pipeline, an evaluation harness, and an empirical analysis of reliability across accuracy, faithfulness, abstention, robustness, cost, and deployment feasibility.

That is the coherent research proposal I would take forward.