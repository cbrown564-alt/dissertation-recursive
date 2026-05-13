# Condition-Card Registry

**Date:** 2026-05-13  
**Status:** Initial registry for the final clarification study  
**Source agenda:** `docs/58_phase_review_research_agenda.md`, section 10.1  
**Purpose:** Decompose named systems into comparable experimental components before interpreting new runs.

This registry treats condition names as bundles, not explanations. A result such
as "H7 beat H6" is only claim-bearing when the changed components are known and
the comparison is either a controlled one-axis contrast or explicitly labelled
as bundled and exploratory.

## Component Role Key

- **Intervention:** the component intentionally being tested.
- **Control:** a component intentionally held fixed to isolate another axis.
- **Nuisance factor:** a component that varies but was not the intended causal
  question; it can confound interpretation.
- **Measurement policy:** scorer, projection, normalization, evidence, or
  benchmark handling that changes how outputs are evaluated.

## Registry Summary

| Condition | Source phase | Implicit research question | Principal intervention | Claim type permitted |
|---|---|---|---|---|
| S2 | Phase 1 / Milestone 3 | Can direct canonical JSON with evidence serve as the primary cost-effective frontier baseline? | Direct full-schema evidence extraction | Benchmark, metrological, baseline |
| E3 | Phase 1 / Phase 2 | Does event-first extraction with constrained LLM aggregation improve reliability over direct extraction? | Event-first decomposition plus LLM aggregation | Benchmark, robustness, exploratory causal only |
| H6 | Phase 1 / Phase 3 | Can compact benchmark-only output reduce schema burden and make local deployment viable? | Single-pass compact closed-label prompt | Deployment, benchmark |
| H6fs | Phase 3 | Do few-shot seizure-status examples reduce over-inference and seizure-free errors? | Few-shot guidance added to H6 | Prompt-engineering signal |
| H6full | Final full-field / MA_v2 | Can H6 retain local viability while restoring structured medication and investigation fields? | Expanded H6 output schema | Benchmark, deployment, measurement-policy-sensitive |
| H7 | Phase 1 | Does separating clinical fact extraction from benchmark normalization improve hard fields? | Extract-then-normalize two-pass decomposition | Decomposition signal |
| D3 | Phase 1 | Does permissive candidate generation plus closed-world verification improve quality? | Candidate-plus-verifier decomposition | Decomposition/verifier signal |
| H8 | Phase 1 | Does removing evidence burden from first-pass extraction and resolving evidence later improve recall? | Evidence-later workflow | Evidence-design signal |
| MA_v1 | Phase 4 | Does the full four-role multi-agent pipeline improve over direct/event-first baselines? | Segmentation, parallel specialists, verifier, aggregator | Multi-agent negative result for this design |
| MA-A | MA_v2 | Does verifier-only augmentation improve an existing strong extractor under matched compute? | Verifier/corrector added to H6full/E3 | Multi-agent signal only with SAS control |
| MA-B | MA_v2 proposed | Do parallel field specialists plus a judge avoid MA_v1 segmentation losses? | Field-specialist parallelism | Exploratory until implemented |
| MA-C | MA_v2 proposed | Does debate/ensemble extraction beat single-agent self-consistency at matched budget? | Debate/ensemble synthesis | Exploratory until implemented |
| MA-D | MA_v2 proposed | Can routing or retrieval choose better specialist harnesses per document/task? | Dispatcher plus retrieval | Exploratory until implemented |
| Gan direct | Phase 5 | What is the direct-label baseline for seizure-frequency normalization? | Single-call normalized frequency label | Frequency benchmark baseline |
| Gan CoT | Phase 5 | Does reasoning improve frequency normalization over direct labelling? | Chain-of-thought/structured reasoning | Prompt-engineering signal |
| Gan few-shot | Phase 5 | Do hard-case examples improve cluster/range/unknown/no-reference frequency cases? | Hard-case few-shot examples | Prompt-engineering negative signal |
| Gan retrieval-highlight | Phase 5 | Does highlighted relevant context improve frequency normalization? | Retrieval-highlight salience cues | Retrieval signal |

## Condition Cards

### S2: Direct Canonical JSON With Evidence

- **Source/predecessor:** Milestone 3 direct baseline; Phase 1 H0/D0.
- **Implicit research question:** Can a small frontier model produce schema-valid,
  evidence-grounded clinical extraction directly from the full letter at low cost?
- **Intended comparator:** E3 for architecture; S3 for format; larger frontier
  H0 runs for model scale.
- **Component taxonomy:** GPT-4.1-mini frontier model; full ExECTv2 canonical
  task scope; full letter plus sentence list; internal-labelled canonical prompt;
  mostly open extraction with scorer-side normalization; strict canonical JSON;
  evidence required at extraction time; model-side normalization plus scorer
  normalization; current/uncertain/not-stated instructions; no special
  abstention module; single pass; one call; native canonical output; corrected
  scorer with collapsed labels and evidence-support reporting where available.
- **Role markings:** base model = control in S2/E3; full schema = control in
  original primary comparison; evidence-at-extraction = intervention/control
  depending on comparison; internal prompt labels = nuisance; corrected scorer
  and collapsed labels = measurement policy.
- **Expected mechanism:** Full-letter context supports holistic diagnosis and
  direct evidence grounding.
- **Expected failure mode:** Context bleeding across family/history/current
  sections; schema burden; temporal/planned medication errors.
- **Hypothesized benefit fields:** diagnosis, quote validity, canonical
  traceability.
- **Regression risk fields:** seizure type, medication temporality, robustness
  traps.
- **Scorer assumptions:** Results depend on corrected medication component
  scoring, ASM synonyms, collapsed seizure labels, and quote validity separate
  from evidence support.
- **Permitted claim:** Strong baseline and metrological claim. Causal claims
  require matched one-axis variants.

### E3: Event-First With Constrained Aggregation

- **Source/predecessor:** Milestone 4 E1/E3; Phase 1 and Phase 2 primary event-first comparator.
- **Implicit research question:** Does extracting temporally qualified events
  before final field aggregation improve field accuracy and robustness over S2?
- **Intended comparator:** S2 on the same model, split, corrected scorer, and
  evidence discipline.
- **Component taxonomy:** GPT-4.1-mini frontier model; full canonical field
  scope; full letter transformed into event list; internal event-first prompts;
  label mapping partly in aggregation; final canonical JSON; evidence required
  in event extraction; LLM constrained aggregation; explicit event temporality;
  implicit abstention; event-first decomposition; two calls; canonical output
  after aggregation; corrected scorer.
- **Role markings:** event list input = intervention; LLM aggregation =
  intervention; base model/split/scorer = controls; extra call count/latency =
  nuisance and cost factor; corrected scorer = measurement policy.
- **Expected mechanism:** Event boundaries reduce negation/family-history
  bleed and help medication/investigation aggregation.
- **Expected failure mode:** Event extraction miss propagates; aggregation can
  drop or misrank candidates; diagnosis context may be fragmented.
- **Hypothesized benefit fields:** medication full tuple, investigations,
  robustness, temporal accuracy.
- **Regression risk fields:** holistic diagnosis, fields requiring global
  context, latency/cost.
- **Scorer assumptions:** E3's advantage is visible only under corrected
  component medication scoring and normalized labels.
- **Permitted claim:** Benchmark and robustness claim for the observed bundle;
  not a pure causal claim about decomposition alone because input
  representation, call budget, and aggregation all change together.

### H6: Benchmark-Only Coarse JSON

- **Source/predecessor:** Phase 1 H6; Phase 3 local direct model workstream.
- **Implicit research question:** Can a compact closed-label prompt recover most
  benchmark performance while avoiding full-schema cost and local-model failures?
- **Intended comparator:** H0/S2 for schema burden; H7/D3 for decomposition;
  H6fs/H6full for prompt/schema variants.
- **Component taxonomy:** frontier or local model depending on run; benchmark
  fields only; full letter; benchmark-facing/internal compact prompt; closed
  label set; relaxed compact JSON; no base evidence; model-side closed-label
  normalization; current-only medication instruction; limited abstention support;
  single pass; one call; relaxed projection to canonical; corrected scorer.
- **Role markings:** compact task scope = intervention; closed label blocks =
  intervention; no evidence = intervention/nuisance depending on claim; relaxed
  projection = measurement policy; local runtime constraints = nuisance.
- **Expected mechanism:** Reduces output burden and forces benchmark-aligned
  labels, especially for local models.
- **Expected failure mode:** Omits dose/unit/frequency and evidence; can hide
  projection effects; may overfit benchmark labels.
- **Hypothesized benefit fields:** medication names, collapsed seizure type,
  diagnosis type, latency.
- **Regression risk fields:** medication full tuple, evidence support, clinical
  usefulness beyond benchmark fields.
- **Scorer assumptions:** Benchmark-only success does not imply full-schema or
  evidence support success.
- **Permitted claim:** Deployment and benchmark-efficiency claim, not full
  clinical extraction claim.

### H6fs: H6 With Few-Shot Seizure Guidance

- **Source/predecessor:** Phase 3 Variant A.
- **Implicit research question:** Do a few examples teaching seizure-free and
  unknown-type behaviour reduce local-model over-inference?
- **Intended comparator:** H6 with the same model, split, prompt style,
  projection, and scorer.
- **Component taxonomy:** Same as H6 except prompt style includes three
  few-shot examples for ambiguous ongoing seizures, seizure-free status, and
  historical type with current seizure freedom.
- **Role markings:** few-shot examples = intervention; model family = control
  only within same-model pairs and nuisance across qwen/gemma comparisons;
  compact schema/projection = controls; corrected scorer = measurement policy.
- **Expected mechanism:** Moves qwen-style models toward benchmark abstention
  and seizure-free labels.
- **Expected failure mode:** Examples displace strong baseline priors in
  gemma/large dense models; helps hard cases while hurting easy majority.
- **Hypothesized benefit fields:** seizure-type collapsed F1, seizure-free
  cases, unknown-type abstention.
- **Regression risk fields:** medication name, diagnosis, routine seizure
  mentions, models already calibrated without examples.
- **Scorer assumptions:** The benefit depends on treating `unknown seizure type`
  and seizure-free behaviour as benchmark compliance rather than unrestricted
  clinical inference.
- **Permitted claim:** Prompt-engineering signal only in same-model H6/H6fs
  pairs. Cross-model H6fs wins are bundled.

### H6full: H6 With Structured Full-Field Output

- **Source/predecessor:** Final full-field workstream and MA_v2 pilot base harness.
- **Implicit research question:** Can the H6 compact strategy be expanded to
  medication tuples, investigations, and frequency without returning to full
  canonical schema burden?
- **Intended comparator:** H6/H6fs for schema expansion; S2/E3 for full-field
  extraction; MA-A for verifier augmentation.
- **Component taxonomy:** frontier or local model; benchmark plus structured
  medication/investigation/frequency fields; full letter; H6-family prompt with
  few-shot/temporality guidance in maintained variants; closed label blocks;
  relaxed structured JSON; optional evidence-bearing projection in clarification
  runs; model-side normalization plus deterministic projection; current-only
  medication and seizure-status guidance; single pass; one call; relaxed or
  evidence-required projection.
- **Role markings:** expanded schema = intervention; H6-family prompt guidance
  = control if fixed, nuisance if mixed with schema comparison; projection
  policy = measurement policy; local runtime = nuisance.
- **Expected mechanism:** Restores medication full-tuple and investigation
  coverage while retaining H6's low cognitive load.
- **Expected failure mode:** Richer schema triggers parse/schema aversion in
  some local families; projection may force-current or drop fields.
- **Hypothesized benefit fields:** medication full tuple, EEG/MRI, diagnosis,
  BenchComp coverage.
- **Regression risk fields:** parse success, latency, evidence support, seizure
  type on schema-averse models.
- **Scorer assumptions:** Interpret as model + projection policy, not raw model
  output alone.
- **Permitted claim:** Full-field benchmark/deployment claim after raw,
  projected, and projection-delta reports are paired.

### H7: Extract-Then-Normalize

- **Source/predecessor:** Phase 1 Stage D; local L3 diagnostic.
- **Implicit research question:** Does separating clinically faithful fact
  extraction from benchmark label mapping improve seizure type and diagnosis?
- **Intended comparator:** H6 on same model/split for decomposition; D3 for
  verifier design; H8 for evidence timing.
- **Component taxonomy:** frontier or local model; benchmark/full selected
  fields depending on version; full letter then rich-fact intermediate; explicit
  two-pass prompts; open clinical facts in pass 1 and closed labels in pass 2;
  rich-fact JSON then normalized JSON; evidence quotes at extraction time;
  model-side normalization in pass 2; explicit current_patient_fact flag;
  limited abstention; two sequential calls; evidence reconstruction/projection.
- **Role markings:** two-pass extraction/normalization split = intervention;
  evidence-at-extraction = control against H8 and intervention against H6;
  extra calls/latency = nuisance; projection = measurement policy; prompt-bug
  versions = nuisance to exclude or flag.
- **Expected mechanism:** Lets the model first preserve clinical language, then
  map to benchmark labels with evidence.
- **Expected failure mode:** Temporal errors in pass 1 propagate; medication
  structure can be stripped by prompt drift; high local latency.
- **Hypothesized benefit fields:** seizure type, label granularity, diagnosis.
- **Regression risk fields:** medication full tuple, planned/current medication,
  local latency.
- **Scorer assumptions:** H7 claims require fixed medication prompt versions and
  evidence reconstruction visible in projection reports.
- **Permitted claim:** Decomposition signal only in matched H6/H7 pairs; bundled
  otherwise because call count, evidence, schema, and projection differ.

### D3: Candidate Plus Verifier

- **Source/predecessor:** Phase 1 Stage E; validation-scale revisit.
- **Implicit research question:** Does permissive candidate extraction followed
  by closed-world verification outperform direct extraction?
- **Intended comparator:** H6 for verifier/decomposition; H7 for rich-fact vs
  candidate architecture; MA-A for verifier-only augmentation.
- **Component taxonomy:** often GPT-5.5 in strongest run; benchmark/full selected
  fields; full letter plus candidate list; candidate prompt then verifier
  prompt; open candidates then closed allowed labels; candidate JSON then
  verified structured JSON; verifier supplies quotes; normalization in verifier;
  current-only and keep/drop rules; two calls; evidence projection.
- **Role markings:** permissive candidate pass = intervention; verifier =
  intervention; GPT-5.5 model in headline result = nuisance when compared with
  GPT-4.1-mini/H6; projection/evidence requirement = measurement policy; token
  budget = nuisance/cost factor.
- **Expected mechanism:** High-recall candidate generation followed by
  precision-oriented keep/drop/normalize decisions.
- **Expected failure mode:** Verifier can retain planned meds as current;
  prompt contract drift can collapse medication tuple output; doubled cost.
- **Hypothesized benefit fields:** medication tuple components, seizure label
  filtering, diagnosis specificity.
- **Regression risk fields:** recall under over-pruning, temporality, latency.
- **Scorer assumptions:** Strong D3 claims require same-model baselines and the
  fixed medication-structure prompt.
- **Permitted claim:** Verifier/decomposition signal when paired; exploratory
  upper-bound when model differs.

### H8: Evidence Later

- **Source/predecessor:** Phase 1 Stage E.
- **Implicit research question:** Does reducing first-pass cognitive load by
  postponing evidence resolution improve extraction recall?
- **Intended comparator:** H7 with same model/split where evidence is captured
  at extraction time.
- **Component taxonomy:** frontier model in tested runs; selected benchmark
  fields; full letter then selected fields; extraction prompt without evidence,
  then evidence resolver prompt; closed benchmark output; evidence resolved in
  pass 2; deterministic/model evidence projection; two calls; corrected scorer.
- **Role markings:** evidence-later = intervention; two-call budget = control
  against H7 but nuisance against H6; evidence projection = measurement policy.
- **Expected mechanism:** Removes quote-copy burden from extraction and adds
  evidence only for selected claims.
- **Expected failure mode:** Evidence retrofitting cannot repair unsupported or
  wrong first-pass claims; underperformed H7 on development.
- **Hypothesized benefit fields:** recall if evidence burden was suppressing
  extraction.
- **Regression risk fields:** evidence support, seizure type, claim grounding.
- **Scorer assumptions:** Quote validity is insufficient; evidence-support
  scoring is required before claiming evidence benefit.
- **Permitted claim:** Negative evidence-design signal: in tested setup,
  extraction-time evidence was better than evidence-later.

### MA_v1: Four-Stage Multi-Agent Pipeline

- **Source/predecessor:** `docs/36_multi_agent_pipeline_plan.md`; Phase 4 MA0-MA3.
- **Implicit research question:** Does explicit section/timeline segmentation,
  parallel field extraction, verification, and aggregation improve reliability
  over S2/E3/H6-style single pipelines?
- **Intended comparator:** H6fs/H6full local baselines, S2/E3 frontier baselines,
  and validation-scale MA_v1 vs dev-pilot MA_v1.
- **Component taxonomy:** GPT-5.4-mini, GPT-5.5, or qwen35 local; full field
  scope; segmented sections and field-specific contexts; multiple specialist
  prompts; closed benchmark labels in downstream stages; multi-stage JSON;
  verifier evidence; normalization distributed across specialists/verifier;
  segmentation-based temporality handling; multi-agent four-stage
  decomposition; 4+ calls; projection to canonical; corrected scorer plus MA
  stage metrics.
- **Role markings:** segmentation = intervention; parallel specialists =
  intervention; verifier/aggregator = intervention; model and call count =
  nuisance unless matched; stage parse/drop/modify rates = measurement policy;
  dev-pilot split = nuisance for validation claims.
- **Expected mechanism:** Isolate current patient sections and reduce per-call
  cognitive load.
- **Expected failure mode:** Product of stage errors, segmentation mistakes,
  over-pruning, aggregation loss, and higher latency.
- **Hypothesized benefit fields:** seizure type in family-history/temporality
  traps, investigations, evidence support.
- **Regression risk fields:** all fields through error propagation; local
  deployability through latency.
- **Scorer assumptions:** Must report per-stage failures and not infer global
  multi-agent failure from one architecture beyond MA_v1.
- **Permitted claim:** Negative result for this specific sequential MA design.

### MA-A: Verifier-Only Augmentation

- **Source/predecessor:** `docs/52_future_work_multi_agent_exploration.md`; MA_v2 pilot.
- **Implicit research question:** Can a minimal verifier/corrector improve a
  strong existing extractor, and is the gain more than matched single-agent
  compute?
- **Intended comparator:** Same base harness without verifier; SAS long-CoT and
  best-of-N controls under matched token/latency budgets.
- **Component taxonomy:** H6full or E3 base; full letter and base JSON given to
  verifier; benchmark-aware verifier/corrector prompts; base schema preserved;
  evidence required for modified fields in proposed fix; normalization should
  share scorer label/synonym worldview; verifier/corrector decomposition; +1 to
  +2 calls; canonical projection; EABC and conditional accuracy metrics.
- **Role markings:** verifier/corrector = intervention; base extractor = control;
  added token budget = nuisance unless SAS matched; EABC and conditional
  base-correct/base-wrong analysis = measurement policy.
- **Expected mechanism:** Catch temporality, family-history, unsupported, and
  component-level medication errors that the base extractor misses.
- **Expected failure mode:** Verifier has little opportunity on strong base
  models; over-flags correct benchmark-normalized values; adds communication
  bottleneck.
- **Hypothesized benefit fields:** local-model seizure type, medication
  components, evidence support.
- **Regression risk fields:** MRI/EEG if corrected unnecessarily, latency, EABC.
- **Scorer assumptions:** Any MA-A superiority claim requires matched SAS control
  and validation-scale confirmation.
- **Permitted claim:** Model-dependent verifier signal; not a general MA claim.

### MA-B: Parallel Field Specialists With Judge

- **Source/predecessor:** MA_v2 proposed design.
- **Implicit research question:** Can field-specialist parallelism reduce
  cognitive load without MA_v1's segmentation error channel?
- **Intended comparator:** H6full/E3 base and SAS matched-budget specialist-style
  prompt; MA_v1 for segmentation vs no-segmentation contrast.
- **Component taxonomy:** full letter sent to each specialist; field-specific
  prompts; judge sees specialist JSON; no explicit segmentation stage; closed
  labels per field; evidence policy not yet locked; parallel calls plus judge;
  projection to canonical.
- **Role markings:** specialist parallelism = intervention; judge = intervention;
  absence of segmentation = intervention relative to MA_v1; prompt richness and
  schema aversion = nuisance; matched-budget SAS = required control.
- **Expected mechanism:** Each extractor attends to one field family while
  preserving full-letter context.
- **Expected failure mode:** Specialists disagree on temporality; judge lacks
  original nuance; schema-rich prompts may fail on gemma-like models.
- **Permitted claim:** Exploratory only until implemented with parse gates and
  matched compute.

### MA-C: Debate / Ensemble Extraction

- **Source/predecessor:** MA_v2 proposed design, motivated by matched-budget MA literature.
- **Implicit research question:** Does independent extraction plus debate beat
  single-agent self-consistency under the same budget?
- **Intended comparator:** Single-agent best-of-k or majority vote using the same
  total token/latency budget.
- **Component taxonomy:** multiple extractor calls over same full letter; debate
  or synthesis judge; same prompt or diverse prompts; output schema inherited
  from base; evidence policy inherited or judge-enforced; projection to canonical.
- **Role markings:** independent samples = intervention; debate judge =
  intervention; extra compute = nuisance unless matched; selection rule =
  measurement policy.
- **Expected mechanism:** Disagreement exposes ambiguity and reduces single-sample
  errors.
- **Expected failure mode:** Debate loses correct minority answer; more tokens
  explain apparent gains; late binding failures.
- **Permitted claim:** Only valid if it beats self-consistency under matched
  budget.

### MA-D: Hierarchical Dispatcher With Retrieval

- **Source/predecessor:** MA_v2 proposed design; Phase 5 retrieval-highlight finding.
- **Implicit research question:** Can a router or retrieval layer choose better
  context/harnesses for letter types or field profiles?
- **Intended comparator:** Retrieval-highlight single-pass baseline before any
  full dispatcher; S2/E3/H6full fixed harnesses.
- **Component taxonomy:** router classifies document or field profile; retrieval
  highlights relevant spans while preserving full letter; specialist harnesses
  selected per route; output schema varies by selected harness then canonicalized.
- **Role markings:** retrieval-highlight = intervention; routing = intervention;
  specialist harness choice = nuisance unless one-axis; projection = measurement
  policy.
- **Expected mechanism:** Retrieval improves salience; routing exploits
  field/document heterogeneity.
- **Expected failure mode:** Router errors; retrieval-only context replacement
  loses global information; bundled route+harness changes obscure causality.
- **Permitted claim:** Retrieval should be tested first as a one-axis ablation;
  dispatcher claims are exploratory until routing is isolated.

### Gan Direct Label

- **Source/predecessor:** Phase 5 G1/G2.
- **Implicit research question:** What is the minimal direct normalized-label
  baseline for Gan seizure-frequency extraction?
- **Intended comparator:** Gan CoT, few-shot, and retrieval-highlight on the same
  model/subset with locked Gan metrics.
- **Component taxonomy:** GPT-4.1-mini, GPT-5.5, qwen35, or other model; Gan
  seizure-frequency-only scope; full Gan synthetic letter; minimal instruction;
  Gan normalized label taxonomy; single label/prose output; optional quote in
  some variants excluded here; model performs normalization; one call; Gan
  Purist/Pragmatic scorer.
- **Role markings:** direct prompt = control; model family = nuisance across
  model comparisons; Gan metric lock = measurement policy.
- **Expected mechanism:** Establish non-reasoning baseline.
- **Expected failure mode:** Cluster/range/history patterns read superficially.
- **Permitted claim:** Frequency baseline only; not comparable to ExECTv2
  full-field results without benchmark reconciliation.

### Gan CoT Label

- **Source/predecessor:** Phase 5 G2/G4.
- **Implicit research question:** Does explicit reasoning improve normalized
  seizure-frequency categorization over direct labelling?
- **Intended comparator:** Gan direct on the same model, subset, output budget,
  and locked metric.
- **Component taxonomy:** Same as Gan direct except prompt asks for reasoning or
  structured analysis before final label; one call; higher output-token budget
  needed for reasoning models.
- **Role markings:** reasoning prompt = intervention; max-output-token setting =
  nuisance/required control; Gan scorer = measurement policy.
- **Expected mechanism:** Better arithmetic, temporal handling, and cluster
  interpretation.
- **Expected failure mode:** Reasoning budget exhaustion, verbose output parsing,
  overthinking easy examples.
- **Permitted claim:** Controlled prompt-engineering claim only when token budget
  is matched and parse failures are included.

### Gan Few-Shot Hard Cases

- **Source/predecessor:** Phase 5 G3.
- **Implicit research question:** Do hard-case examples for clusters, ranges,
  seizure-free intervals, unknown, and no-reference cases improve frequency
  normalization?
- **Intended comparator:** Gan CoT/direct carry-forward on the same 50-document
  controlled subset.
- **Component taxonomy:** Gan frequency-only; full letter; hard-case examples
  added to direct/label prompt; same normalized label taxonomy; one call; Gan
  scorer.
- **Role markings:** few-shot examples = intervention; example mix = nuisance if
  not field-balanced; Gan metric = measurement policy.
- **Expected mechanism:** Teach rare pattern handling.
- **Expected failure mode:** Harms easy-majority distribution; model-specific
  few-shot regression, as observed in H6fs/gemma.
- **Permitted claim:** Negative prompt-engineering signal for this example set;
  not proof that all few-shot frequency prompts fail.

### Gan Retrieval-Highlight

- **Source/predecessor:** Phase 5 G4 fixed run.
- **Implicit research question:** Does highlighting retrieved frequency-relevant
  spans improve normalization while preserving the full letter?
- **Intended comparator:** Gan direct and Gan CoT with same model, subset, token
  budget discipline, and locked metric; retrieval-only ablation.
- **Component taxonomy:** GPT-5.5 or qwen35; Gan frequency-only; full letter plus
  highlighted retrieved spans; retrieval-highlight prompt; Gan normalized label;
  usually evidence/quote visible; model performs normalization aided by
  retrieved salience; one call plus deterministic retrieval; Gan scorer.
- **Role markings:** highlighted spans = intervention; deterministic retriever =
  intervention/control depending on tuning; full letter retained = control
  against retrieval-only; max-output-token setting = nuisance; Gan scorer =
  measurement policy.
- **Expected mechanism:** Directs attention to seizure-free intervals,
  cluster-disambiguating spans, and relevant frequency mentions.
- **Expected failure mode:** Retriever misses key span or over-highlights
  misleading history; category-boundary errors remain.
- **Permitted claim:** Retrieval signal for Gan frequency. Transfer to ExECTv2
  medication/seizure type remains untested and requires ablation.

## Controlled vs Bundled Comparisons

| Comparison | Status | What it can support |
|---|---|---|
| H6 vs H6fs, same model/split/scorer/projection | Controlled one-axis | Effect of adding the few-shot seizure guidance for that model family |
| Gan direct vs Gan CoT, same model/subset/token budget | Controlled one-axis if output budget fixed | Effect of reasoning prompt on Gan frequency |
| Gan direct/CoT vs Gan retrieval-highlight, same model/subset and full letter retained | Mostly controlled | Effect of retrieval-highlight salience, with deterministic retriever as part of intervention |
| H7 vs H8, same model/subset | Mostly controlled | Evidence-at-extraction vs evidence-later, with similar two-call budget |
| S2 vs S3 | Controlled one-axis | Model-facing output format, because canonical scoring remains JSON |
| S2 vs E3 | Bundled | Direct vs event-first plus event representation, aggregation call, and call-budget change |
| H6 vs H7 | Bundled unless specially matched | Single-pass closed-label vs two-pass rich-fact normalization, evidence timing, call budget, and projection |
| H6 vs D3 | Bundled unless specially matched | Candidate/verifier architecture plus call count, evidence, and often model differences |
| H6 vs H6full | Bundled unless prompt text fixed | Schema breadth/full-field burden plus projection and possibly evidence policy |
| H6fs qwen vs H6fs gemma | Bundled | Model-family sensitivity, not prompt effect alone |
| MA_v1 vs H6fs/H6full | Bundled | Multi-agent architecture plus call budget, latency, segmentation, verifier, and aggregation |
| MA-A vs SAS long-CoT | Controlled if token/latency matched | Verifier/corrector value beyond extra compute |
| MA-B/C/D vs historical baselines | Bundled until matched controls exist | Exploratory architecture signals only |
| Gan retrieval-highlight vs ExECTv2 H6/H7/E3 | Invalid direct comparison | Different benchmark/task; only motivates transfer experiments |

## Ablations Required Before Strong Claims

### Prompt Engineering

Required before claiming prompt-engineering benefit:

1. Same-model H6 vs H6fs on the same document slice, scorer, prompt style, and
   projection policy.
2. Internal-labelled vs clinician-facing prompt A/B for H6fs/H6full, already
   represented by FC01/FC07 and FC04/FC08.
3. Few-shot hard-case ablation by model family, because qwen, gemma, dense, and
   MoE models responded differently.
4. Report raw and projected scores separately so prompt gains are not projection
   artifacts.

### Decomposition

Required before claiming decomposition helps:

1. H6/H6full vs H7 on the same model and prompt style, with evidence policy and
   projection deltas reported.
2. H6/H6full vs D3 on the same model, using the fixed structured-medication
   verifier prompt.
3. H7 vs D3 to separate rich-fact normalization from permissive-candidate
   verification.
4. H7 vs H8 to isolate evidence timing from two-call decomposition.
5. Matched call/token/latency reporting; otherwise gains may be compute effects.

### Multi-Agent Design

Required before claiming multi-agent benefit:

1. MA-A validation-scale run against SAS long-CoT or best-of-N with matched token
   and latency budgets.
2. Conditional analysis: what happens when the base extractor was already
   correct vs wrong?
3. Stage-level parse/drop/modify rates, with over-drop abort thresholds.
4. MA-B/C/D must each include a matched SAS control and should not be compared
   only with historical single-call baselines.
5. Retrieval-highlight single-pass ablation should precede MA-D routing claims.

### Retrieval

Required before claiming retrieval benefit beyond Gan frequency:

1. ExECTv2 retrieval-highlight variants for medication, seizure type, and
   diagnosis, preserving the full letter plus highlighted spans.
2. Retrieval-only ablation to confirm retrieved spans are cues, not sufficient
   replacement context.
3. Same-model direct/H6full comparator with identical prompt style and scorer.
4. Error audit separating retriever miss, misleading highlight, and model
   normalization error.

## Claim Guardrails

- Treat every named harness as **model + prompt + schema + projection + scorer**.
- Do not call a comparison causal unless only one intended intervention changes.
- Any result involving relaxed or evidence-required projection must be reported
  with raw-output score and projection-delta companion reports.
- Any evidence claim must use evidence support, not quote validity alone.
- Any Gan-to-ExECTv2 inference is a transfer hypothesis until benchmark
  reconciliation and ExECTv2 retrieval ablations are complete.
