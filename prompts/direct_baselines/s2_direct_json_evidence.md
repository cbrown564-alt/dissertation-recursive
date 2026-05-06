# S2 Direct JSON Extraction With Evidence

You are extracting structured information from an epilepsy clinic letter.

Return only one JSON object matching the canonical extraction schema. Do not
wrap the response in Markdown. Use `pipeline_id: "S2_direct_json_evidence"`.

Every present field must include exact evidence quotes copied from the source
letter. Evidence quotes must be contiguous text from the letter. Include
`sentence_id`, `char_start`, and `char_end` when you can identify them from the
provided sentence list; otherwise use `null`.

Create evidence-grounded events for medication, seizure frequency, seizure
type, EEG/MRI investigation, and diagnosis claims. Final fields should cite
supporting event IDs in `evidence_event_ids`.

Do not infer values from clinical knowledge. Use `not_stated` when the letter
does not state the field and use `uncertain` when relevant text exists but the
value cannot be resolved.
