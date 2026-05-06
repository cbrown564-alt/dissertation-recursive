# E1 Event Extraction

You are extracting evidence-grounded clinical events from an epilepsy clinic
letter.

Return only one JSON object. Do not wrap the response in Markdown. Use
`pipeline_id: "E1_event_extraction"`.

The object must contain:

- `document_id`
- `pipeline_id`
- `events`
- `metadata`

Extract events only. Do not emit final patient-level fields.

Required event categories:

- `medication`
- `seizure_frequency`
- `seizure_type`
- `investigation`
- `diagnosis`

Every event must include:

- `id`: stable within this document, for example `ev_m01`
- `category`
- `temporality`
- `status`
- `value`
- `evidence`

Evidence quotes must be exact contiguous text copied from the source letter.
Include `sentence_id`, `char_start`, and `char_end` when available from the
sentence list; otherwise use `null`.

Medication events should preserve `medication_name`, `dose`, `dose_unit`,
`frequency`, and `reason_stopped` when stated. Use statuses `current`,
`previous`, `stopped`, `declined`, `planned`, `increased`, `reduced`,
`uncertain`, or `not_stated`.

Investigation events should preserve `investigation_type` as `EEG` or `MRI`,
separate `status` from `result`, and use `result` only for `normal`,
`abnormal`, `not_stated`, or `uncertain`.

Seizure-frequency events should preserve `temporal_scope` and linked
`seizure_type` where stated.

Do not infer values from clinical knowledge. Omit unsupported events rather
than inventing them.
