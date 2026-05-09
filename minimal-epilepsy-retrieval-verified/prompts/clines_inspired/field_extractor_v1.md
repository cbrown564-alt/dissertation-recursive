# CLINES-Inspired Field Extractor Prompt v1

You are extracting clinical information from a section-aware context drawn from
an epilepsy clinic letter.

The context below is derived from document sections most likely to contain the
target field family. Use it as your primary evidence source; only use the full
letter if the section context is explicitly insufficient.

For the requested field family, extract only what is directly stated. Return
JSON with keys matching the target fields listed with the prompt.

For each extracted value include:
- The extracted value.
- An exact supporting quote from the context as `evidence` (the verbatim
  phrase from the letter, not a paraphrase).
- Whether the finding appears to be current or historical as `status`:
  one of `current`, `historical`, or `unknown`.
- A `confidence` score from 0 to 1.
- A `warnings` list for any ambiguity, missing evidence, or extraction
  uncertainty.

If the information is absent from the context, return the field as `null` or
an empty list. Do not invent or infer clinical facts that are not stated.
Do not copy or paraphrase values across field families.
