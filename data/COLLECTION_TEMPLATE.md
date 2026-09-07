# Field Data Collection Template

Use this template to record real **Cameroonian Francanglais** statements heard
around Yaounde (taxis, chop houses, roadside businesses, bendskins, university,
and other ordinary interactions). Francanglais is the single target variety;
its French, English, Pidgin, and local-language influences are not separate datasets.
Each entry must match the fields validated by `validate_import` in
`src/yaounde_analyzer/core/corpus.py`.

## Collection And Review

- Split collection across the three group members, aiming for five statements each
   and a final set of 10-15 reviewed, authentic Francanglais statements.
- Explain the coursework and obtain appropriate permission before recording or
   retaining identifiable conversation. Public quotation needs separate approval.
   Use anonymous identifiers and avoid sensitive or unsafe collection situations.
- Have a second Francanglais-familiar member review the exact transcription and
   target-variety suitability. Record uncertainty or disagreements separately;
   do not decide suitability by counting borrowed English words alone.
- Record real observation context/date when known in private collection notes.
   The record's `created_at` is its creation time, not automatically the observation
   time. Keep consented audio private; the first app release does not upload audio.
- Keep doubtful/out-of-scope observations separate from the final corpus. Do not
   alter their wording to force a Francanglais classification or successful parse.

The target is fixed to `cameroon_francanglais`; other explicit targets and unknown
fields are rejected. Older records without a target default to Francanglais without
changing their raw text. This is a scope declaration, not automatic language detection.
Reviewer fields are still planned; keep review notes separately for now.

## Rules

1. **Write down the exact words spoken.** Keep slang, code-mixing, accents,
   incomplete sentences, and mistakes exactly as heard. Do not correct,
   translate, or clean up the wording.
2. **`source_kind` must be `"field"`** for real collected statements (never
   `"demo"`).
3. **`manual_transcription_attested` must be `true`.** This is only valid if
   you personally listened and transcribed the statement yourself. A `"field"`
   record without this set to `true` will be rejected on import. This declaration
   does not independently prove authenticity; observation and peer review are required.
4. **`topics`** is a list drawn from: `commuting`, `internet`, `electricity`,
   `market_bargaining`, `rain`, `fuel`, `roadside_business`, `bendskin`,
   `security`, `university`. A statement may have more than one topic.
5. **`collector_id`** is the name/initials of whoever transcribed it, for
   accountability.
6. Each `statement_id` must be unique within the batch (e.g. `field-001`,
   `field-002`, ...).

## Record Template

```json
{
  "statement_id": "field-001",
  "revision": 1,
  "source_kind": "field",
   "target_variety": "cameroon_francanglais",
  "raw_text": "<exact transcribed statement>",
  "manual_transcription_attested": true,
  "collector_id": "<your name or initials>",
  "topics": ["commuting"],
  "created_at": "<ISO 8601 timestamp, e.g. 2026-09-10T14:30:00Z>"
}
```

## Target

10-15 reviewed Francanglais statements per group, covering as many of the topics
above as naturally occur. Do not invent statements to fill a topic quota; only
record what was actually heard. Synthetic examples remain labelled `"demo"` and
cannot count toward this target, even when their wording sounds plausible.

This deliberately narrows the assignment's broader multilingual framing. Confirm
the Francanglais-only interpretation with the instructor while retaining the
Yaounde setting and all required lexical/syntactic deliverables.
