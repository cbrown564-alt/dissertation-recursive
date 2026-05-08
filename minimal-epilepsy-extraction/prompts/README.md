# Prompt Snapshots

The authoritative prompts live in source so reruns cannot drift from the
executed harness:

- h008 guarded prompt: `src/epilepsy_agents/broader_field_schema.py`
  - `tier1a_system_prompt()`
  - `tier1a_user_prompt(letter)`
- h013 production prompts:
  - seizure frequency: `src/epilepsy_agents/llm_pipeline.py`, `SinglePromptLLMPipeline`
  - broader fields: `src/epilepsy_agents/broader_field_schema.py`, `broader_coverage_user_prompt(letter)`
  - epilepsy classification: `src/epilepsy_agents/production_schema.py`

The `.txt` files in this directory are human-readable snapshots of the important
contract, not separate runtime inputs.
