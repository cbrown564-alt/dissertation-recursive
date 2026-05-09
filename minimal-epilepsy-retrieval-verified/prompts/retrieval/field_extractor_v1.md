# Retrieval Field Extractor Prompt v1

You are given retrieved context passages from a clinic letter and the name of a
target field family.

Extract only the requested field family from the retrieved context.
Return JSON with keys matching the target fields listed below the prompt.

For each extracted value include:
- The extracted value.
- An exact supporting quote from the context as `evidence`.
- A `confidence` from 0 to 1.
- A `warnings` list.

If the information is absent from the context, return the field as `null` or an
empty list. Do not invent missing clinical facts.
