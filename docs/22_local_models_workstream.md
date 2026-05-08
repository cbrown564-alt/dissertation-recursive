# Local Models (Ollama) Workstream

**Date:** 2026-05-08  
**Motivation:** All experiments to date use closed frontier APIs (OpenAI, Anthropic, Google).
A dissertation contribution of independent significance is demonstrating that a locally-hosted
open-weight model can achieve competitive performance — reducing cost to near-zero marginal,
removing data-privacy constraints, and enabling offline deployment in clinical settings.  
**Target models:** Qwen 2.5 9B and/or Qwen 3 4B (via ollama label `qwen`), Gemma 3 4B
(`gemma3:4b` or equivalent). Both run on a local machine via ollama's OpenAI-compatible API.  
**Goal:** Determine whether any local model × harness combination achieves ≥ 0.70 on
`medication_name_f1` and ≥ 0.50 on `seizure_type_f1_collapsed` — two benchmark-aligned fields
where frontier models currently reach 0.847–0.872 and 0.469–0.633 respectively.

---

## Background

### Why local models are harder

Local models (≤ 9B parameters at 4-bit quantization) face structural disadvantages on this task:

| Challenge | Implication |
|---|---|
| Weaker instruction following | May not produce canonical JSON without enforcement |
| Smaller context windows | Typical 4K–8K effective context; long clinical letters may truncate |
| Less clinical pre-training | Drug names, seizure taxonomy, epilepsy terminology less reliable |
| Lower structured-output reliability | JSON schema enforcement requires model cooperation |
| Higher hallucination rate | May generate plausible-but-wrong ASM names or seizure types |
| No native JSON schema enforcement | Ollama supports `format: json` but not arbitrary schema |

These challenges make harness selection more important than for frontier models: a strict
canonical schema (H0) will fail on local models more often; simpler, more guided prompts
should be tried systematically.

### Ollama API surface

Ollama exposes an OpenAI-compatible API at `http://localhost:11434/v1`. This means the existing
`OpenAIAdapter` in `src/model_providers.py` can be reused with `base_url` overridden, or a
thin `OllamaAdapter` subclass can handle ollama-specific parameters (`format: json`,
context window truncation).

Key differences from the OpenAI API:
- `format: "json"` enforces JSON output (not schema-constrained, just syntactically valid JSON)
- No native JSON schema enforcement (unlike OpenAI's `response_format.json_schema`)
- Context window is set per-model pull; verify with `ollama show <model>`
- Pricing: $0 marginal cost per call (hardware depreciation only)

---

## Target Models

Register all local models in `configs/model_registry.yaml` following the existing schema.

| Study label | Ollama model tag | Parameters | Context | Notes |
|---|---|---|---|---|
| `qwen_9b_local` | `qwen2.5:9b` or `qwen3:9b` | 9B (Q4_K_M) | 8K–128K | Strong instruction following for open-weight class |
| `qwen_4b_local` | `qwen2.5:3b` or `qwen3:4b` | 4B (Q4_K_M) | 8K | Smaller; faster; lower quality expected |
| `gemma_4b_local` | `gemma3:4b` | 4B effective | 8K | Google family; different clinical vocabulary |

Ollama `pricing` fields:
```yaml
input_price_per_million: null
output_price_per_million: null
billing_currency: "local"
```

Set `structured_output: "json_mode"` (ollama format=json, not schema-constrained).

Before running any experiments, verify each model is pulled and can respond:
```bash
ollama run qwen2.5:9b "What is levetiracetam?"
ollama run gemma3:4b "What is levetiracetam?"
```

---

## Infrastructure Changes

### 1. OllamaAdapter (`src/model_providers.py`)

Add a new `OllamaAdapter` class that:
- Uses the `openai` SDK with `base_url="http://localhost:11434/v1"` and `api_key="ollama"`.
- Passes `model=request.model.provider_model_id` directly (ollama model tag).
- When `request.schema_mode == "json_mode"`: adds `response_format={"type": "json_object"}` to
  the chat completions call. This is the closest ollama equivalent to schema enforcement.
- Truncates the prompt to `context_window_tokens - max_output_tokens` if the model has a
  declared context window and the prompt exceeds it. Logs a `context_truncated: true` flag.
- Reports `input_tokens` / `output_tokens` from the response `usage` field (ollama does populate
  this).
- Sets `estimated_cost` to `{"currency": "local", "total": 0.0, "status": "local_compute"}`.
- Registers as `provider: "ollama"` in `adapter_for()`.

No changes required to `ModelRequest`, `ModelResponse`, or `TokenUsage` — the dataclasses are
already provider-neutral.

### 2. Model registry entries (`configs/model_registry.yaml`)

Add a section for local models following the existing format. Set `provider: ollama`,
`api_surface: openai_compat`, and `context_window_tokens` to the model's pulled context.

### 3. Prompt truncation utility

Clinical letters vary in length. Add a `truncate_to_context(prompt: str, model: ModelSpec) -> str`
utility in `model_providers.py`:
- If `model.context_window_tokens` is None, return prompt unchanged.
- Otherwise, estimate token count (character count / 4 as a proxy) and truncate the document
  section only (preserve system instructions and schema).
- Log a warning when truncation occurs.

### 4. Runner changes (`src/model_expansion.py` or new `src/local_models.py`)

The existing `run_one()` function is already provider-neutral. The only change is:
- Route `provider: "ollama"` to the new `OllamaAdapter` in `adapter_for()`.
- Add `--ollama-base-url` CLI flag (default `http://localhost:11434/v1`) so the URL is
  configurable without code changes.

---

## Harness Selection Strategy

Local models need simpler harnesses. The following are listed in order from most to least
constrained, with expected success rate for a 9B model:

| Harness | Description | Expected success (9B) | Risk |
|---|---|---|---|
| `H0_strict_canonical` | Full canonical JSON + evidence quotes | Low (30–60%) | Many schema failures, missing evidence |
| `H4_provider_native_structured` | JSON mode (format=json) + coarse schema | Medium (60–80%) | May produce valid JSON but wrong structure |
| `H6_benchmark_only_coarse_json` | Benchmark fields only, minimal schema | Medium-high (70–85%) | Less complex task; still needs JSON |
| `H3_loose_answer_then_parse` | Prose/list output, deterministic parser | High (85–95%) | Parser quality determines scoring; no evidence |
| `H7_extract_then_normalize` | Two-pass: extract raw, normalize to canonical | Medium-high (70–85%) | First pass may hallucinate; second pass anchors |

Test harnesses in this order. Do not promote H0 if parse success is < 0.80.

---

## Stage L0: Ollama Setup and Connectivity Verification

**Purpose:** Verify the local infrastructure before spending experiment time.

**Actions:**
1. Confirm ollama is running: `curl http://localhost:11434/api/tags`.
2. Pull target models if not present:
   ```bash
   ollama pull qwen2.5:9b
   ollama pull gemma3:4b
   ```
3. Record exact model metadata:
   ```bash
   ollama show qwen2.5:9b --modelfile
   ollama show gemma3:4b --modelfile
   ```
   Save to `runs/local_models/stage_l0/model_metadata.json`.
4. Run a 1-document stub test through the new `OllamaAdapter` using `H0` and `H4` harnesses.
   Verify: response received, token counts logged, cost logged as local.
5. Check prompt length for the 15 dev documents against the model context window. Flag any
   docs that would exceed context.

**Exit criterion:** Both models respond successfully on the stub document. Context warning is
logged (or confirmed not needed) for all dev docs.

**Outputs:**
- `runs/local_models/stage_l0/model_metadata.json`
- `runs/local_models/stage_l0/connectivity_report.md` (5–10 lines: status, context headroom)

---

## Stage L1: H0 Baseline on Development Docs

**Purpose:** Establish how badly strict canonical extraction fails on local models. This is
expected to be poor — the goal is characterizing the failure modes, not achieving good results.

**Design:**

| Axis | Values |
|---|---|
| Models | `qwen_9b_local`, `gemma_4b_local` |
| Harness | `H0_strict_canonical` |
| Split | Development (15 docs) |
| Repeats | 1 |

**Metrics to record:**
- Parse success rate (does the output parse as valid JSON?)
- Schema validity rate (does parsed JSON match the canonical schema?)
- Quote validity rate (are evidence quotes locatable in the document?)
- `medication_name_f1`, `seizure_type_f1_collapsed`, `epilepsy_diagnosis_accuracy`
- Context truncation rate

**Expected findings:**
- Parse success: 30–70% (models often produce malformed JSON or wrapped JSON)
- Schema validity: lower than parse success (missing required fields, wrong types)
- Quote validity: low (local models often hallucinate quotes)

**Analysis:** Categorize failures into: malformed JSON, schema mismatch, empty fields, wrong
structure, hallucinated quotes. This drives harness selection for L2–L4.

**Outputs:**
- `runs/local_models/stage_l1/comparison_table.csv`
- `runs/local_models/stage_l1/failure_analysis.md`

---

## Stage L2: H4 (JSON Mode) Test

**Purpose:** Test whether enforcing JSON output mode (ollama `format: json`) materially improves
parse success and schema compliance without harming extraction quality.

**Design:**

| Axis | Values |
|---|---|
| Models | `qwen_9b_local`, `gemma_4b_local` |
| Harness | `H4_provider_native_structured_output` (ollama json mode) |
| Split | Development (15 docs) |
| Repeats | 1 |

**H4 configuration for ollama:**
- Set `response_format={"type": "json_object"}` in the chat completions call.
- Keep the H0 prompt unchanged (same instructions, same schema description).
- The model is forced to produce syntactically valid JSON but is not schema-constrained.

**Comparison:** L2 vs L1 on parse success rate and schema validity. If H4 gains ≥ 15pp on
parse success → it becomes the harness of choice for subsequent stages.

**Outputs:**
- `runs/local_models/stage_l2/comparison_table.csv`

---

## Stage L3: Simplified Harnesses (H6, H3, H7)

**Purpose:** Test whether simpler tasks improve extraction quality on local models.

### L3-A: H6 (Benchmark-Only Coarse JSON)

Prompt asks only for the benchmark fields: medication names, seizure types, epilepsy type,
frequency. No evidence quotes. No temporal metadata. No full canonical schema.

This is already implemented as `build_h6_prompt()` in `model_expansion.py`. Use it as-is.

**Expected:** Higher parse and schema success; lower evidence quality (no quotes).

### L3-B: H3 (Loose Answer, Deterministic Parser)

Prompt asks the model to answer in plain language or simple lists. A deterministic parser
converts the output into canonical fields. No JSON required from the model.

This is already implemented as `build_loose_prompt()` in `model_expansion.py`.

**Key adaptation for local models:** The H3 parser must tolerate more output variability. If
the existing parser fails > 20% of the time on local model outputs, extend it to handle:
- Numbered lists (1. levetiracetam 500mg twice daily)
- Bulleted lists with or without dashes
- Natural prose ("The patient takes levetiracetam 500mg twice daily and sodium valproate")

This parser extension is in `model_expansion.py` (the `parse_loose_response()` or equivalent
function). Regression fixtures should cover local model output patterns.

### L3-C: H7 (Two-Pass Extract-Normalize)

H7 is already implemented in `model_expansion.py` (`build_h7_extract_prompt`,
`build_h7_normalize_prompt`). The two-pass approach is specifically well-suited to local models
because:
- Pass 1 (extract) asks only for verbatim quotes — no normalization, no JSON structure.
- Pass 2 (normalize) is given clean extracted text and must produce structured output.
  The normalization task is simpler and more deterministic than end-to-end extraction.

**Key consideration:** The H7 `projected_canonical()` path now produces evidence-grounded
canonical outputs. This should be verified to work with local model outputs before scoring.

**Design for L3:**

| Condition | Model | Harness |
|---|---|---|
| L3-A | `qwen_9b_local` | H6 |
| L3-A | `gemma_4b_local` | H6 |
| L3-B | `qwen_9b_local` | H3 |
| L3-B | `gemma_4b_local` | H3 |
| L3-C | `qwen_9b_local` | H7 |
| L3-C | `gemma_4b_local` | H7 |

**Split:** Development (15 docs), 1 repeat.

**Outputs:**
- `runs/local_models/stage_l3/comparison_table.csv`
- `runs/local_models/stage_l3/harness_selection_decision.md`

**Decision rule:** Promote the best harness per model to Stage L4 if it achieves:
- Parse success ≥ 0.80, AND
- `medication_name_f1` ≥ 0.50, AND
- At least one of: `seizure_type_f1_collapsed` ≥ 0.30 or `epilepsy_diagnosis_accuracy` ≥ 0.50.

If no harness meets these thresholds for a model → that model is documented as insufficient
for this task at this parameter scale, and the reason is analyzed (clinical vocab gap, context
length, instruction following).

---

## Stage L4: Prompt Engineering for Local Models

**Purpose:** Adapt the best harness from L3 with local-model-specific prompt engineering.
This stage runs only on models/harnesses that passed L3.

### L4-A: Clinical Vocabulary Anchoring

Local models may not know that "eplim" is valproate or that "JME" is juvenile myoclonic
epilepsy. Add a vocabulary preamble to the harness prompt:

```
## Anti-seizure medication names
Common ASMs include: levetiracetam (Keppra), sodium valproate (Epilim, Eplim),
lamotrigine (Lamictal), carbamazepine (Tegretol), phenytoin, topiramate, zonisamide,
brivaracetam, lacosamide, oxcarbazepine, perampanel, clobazam, clonazepam.
Normalize brand names to generic names in your output.

## Epilepsy and seizure terminology
Focal seizures: focal aware, focal impaired awareness, focal to bilateral tonic-clonic.
Generalized seizures: generalized tonic-clonic (GTCS), absence, myoclonic, atonic.
Epilepsy syndromes: JME (juvenile myoclonic epilepsy), childhood absence epilepsy (CAE),
Lennox-Gastaut syndrome (LGS), DRAVET syndrome.
```

### L4-B: Structured Output with Schema Hint

For H6 and H4: include the target JSON structure as an explicit example in the prompt (few-shot
schema demonstration), not just a description:

```json
{
  "medication_names": ["levetiracetam", "sodium valproate"],
  "seizure_types": ["focal impaired awareness"],
  "epilepsy_type": "focal epilepsy",
  "current_seizure_frequency": "2 per month"
}
```

This pattern (schema-by-example) works better than schema-by-description for weaker models.

### L4-C: Smaller Context — Letter-Only Prompt

If context truncation is occurring or hurting performance: strip all non-essential prompt
content and pass only the clinical letter + a minimal instruction. Compare against L3 results
to check whether the extra prompt context helps or hurts.

### L4 Design

| Condition | Model | Harness | Prompt variant |
|---|---|---|---|
| L4-A | promoted models from L3 | best harness | + vocabulary preamble |
| L4-B | promoted models from L3 | H6 or H4 | + schema-by-example |
| L4-C | promoted models from L3 | best harness | minimal prompt |

**Split:** Development (15 docs), 1 repeat.  
**Outputs:** `runs/local_models/stage_l4/comparison_table.csv`, `promotion_decision.md`.

**Decision rule:** Promote any L4 variant that exceeds L3 best result by ≥ 0.03 on
`medication_name_f1`. Promote the overall best variant to Stage L5.

---

## Stage L5: Validation-Scale Run

**Purpose:** Formal evaluation of the best local model × harness combination on 40 validation
documents. This produces the dissertation numbers.

**Entry criterion:** At least one local model × harness achieves on development:
- `medication_name_f1` ≥ 0.50
- `seizure_type_f1_collapsed` ≥ 0.30

**Design:**

| Item | Value |
|---|---|
| System | Best model × harness × prompt variant from L4 |
| Split | Validation (40 docs) |
| Repeats | 1 (or 2 if time permits — local compute is free) |
| Scorer | Full Phase 2+3 corrected scorer |

**Comparison table:**

| System | Med Name | Med Full | Sz Collapsed | Dx Acc | Freq Loose | Cost/doc |
|---|---|---|---|---|---|---|
| S2 H0 GPT-4.1-mini (baseline) | 0.852 | 0.655 | 0.610 | 0.725 | 0.075 | ~$0.003 |
| E3 H0 GPT-4.1-mini (baseline) | 0.872 | 0.707 | 0.633 | 0.775 | 0.125 | ~$0.005 |
| [best local model + harness] | TBD | TBD | TBD | TBD | TBD | $0 marginal |

If the local model reaches within 15% of the GPT-4.1-mini baseline on `medication_name_f1`
and `seizure_type_f1_collapsed`, the dissertation can claim competitive local performance.

**Outputs:**
- `runs/local_models/stage_l5/evaluation_summary.json`
- `runs/local_models/stage_l5/comparison_vs_frontier.csv`
- `runs/local_models/stage_l5/claim_package.md` (bounded claim, failure modes, cost analysis)

---

## Stage L6: Size Ablation (Optional)

**Entry criterion:** L5 shows meaningful performance from a local model (≥ 0.60 med name F1).

**Purpose:** Determine whether a smaller or larger model variant is worth the compute tradeoff.

**Design:** Test `qwen_4b_local` (if 9B was primary) or `qwen_14b_local` (if available on
hardware) against the L5 winner using the same harness and prompt.

| Model | Params | Expected quality | Latency |
|---|---|---|---|
| `qwen_4b_local` | ~4B | Lower | Faster |
| `qwen_9b_local` | ~9B | Primary | Medium |
| `qwen_14b_local` | ~14B | Higher (if fits) | Slower |

**Decision:** If 4B model is within 5% of 9B → recommend 4B for deployment. If 14B is
materially better → report as future work (requires larger hardware).

---

## Dissertation Claim Structure

### If local models succeed (≥ 0.70 med name F1 on validation)

> "We demonstrate that a locally-hosted 9B open-weight model achieves [X]% medication name F1
> and [Y]% collapsed seizure type F1 using the [harness] extraction strategy — within [Z]%
> of the GPT-4.1-mini baseline — at zero marginal API cost. This makes the pipeline viable
> for privacy-constrained clinical deployment without internet connectivity."

### If local models show partial success (0.50–0.70 med name F1)

> "Local open-weight models can extract the most common clinical fields with moderate accuracy
> ([X]% medication name F1) but show a material gap ([Z]pp) versus frontier models on
> structured multi-field extraction. The gap is concentrated in [failure modes identified in
> L1–L3]. Clinical vocabulary anchoring and two-pass normalization reduce but do not eliminate
> this gap."

### If local models fail (< 0.50 med name F1)

> "Open-weight models at the 4–9B scale fail to reliably extract structured clinical information
> from epilepsy letters under any harness tested. The primary failure modes are [X]. This
> suggests that clinical information extraction from unstructured specialist letters currently
> requires either frontier models or task-specific fine-tuning, neither of which was within
> scope of this dissertation."

All three outcomes are valid dissertation contributions. The negative result is scientifically
useful — it bounds where the local model capability frontier lies for this clinical NLP task.

---

## Infrastructure Summary

| Component | Change | File |
|---|---|---|
| OllamaAdapter | New adapter class, `format: json` support, context truncation | `src/model_providers.py` |
| `adapter_for()` routing | Add `"ollama"` key | `src/model_providers.py` |
| Local model entries | New YAML entries with `provider: ollama` | `configs/model_registry.yaml` |
| Vocabulary preamble | New `build_vocab_preamble()` helper | `src/model_expansion.py` |
| H3 parser extension | Handle numbered/bulleted lists for local output | `src/model_expansion.py` |
| Context truncation utility | `truncate_to_context()` | `src/model_providers.py` |
| L0–L5 runner | Stage-gated runner, can be new `src/local_models.py` or flags in existing | new file or flags |

---

## Cost Estimate

All model calls are local compute. The only cost is electricity and developer time.

| Stage | Docs × repeats | Wall time (9B model, ~10s/doc) |
|---|---|---|
| L0 (smoke) | 1 | ~1 min |
| L1 (H0 baseline) | 15 × 2 models | ~5 min |
| L2 (H4) | 15 × 2 models | ~5 min |
| L3 (H6/H3/H7) | 15 × 2 models × 3 harnesses | ~15 min |
| L4 (prompt variants) | 15 × promoted conditions | ~10 min |
| L5 (validation) | 40 × 1 | ~7 min |
| L6 (size ablation) | 40 × 2 models | ~14 min |
| **Total** | | **~60 min wall time** |

The 9B model at Q4_K_M quantization requires ~6–8 GB VRAM or ~10–12 GB RAM. Confirm the
machine can serve this before Stage L0.

---

## Priority and Sequence

```
L0 (setup) → L1 (H0 baseline) → L2 (json mode) → L3 (simpler harnesses)
                                                           → L4 (prompt engineering)
                                                                    → L5 (validation scale)
                                                                              → L6 (size ablation, optional)
```

The full pipeline from L0 to L5 can be run in a single day. L6 is conditional on L5 results.
Begin with L0 and L1 to understand the failure landscape before committing to L3–L4.
