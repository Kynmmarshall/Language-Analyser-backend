# Field Data Collection Template

Use this template to record real statements heard around Yaounde (taxis, chop
houses, roadside businesses, bendskins, checkpoints, ICT University, etc.).
Each entry must match the fields validated by `validate_import` in
`src/yaounde_analyzer/core/corpus.py`.

## Rules

1. **Write down the exact words spoken.** Keep slang, code-mixing, accents,
   incomplete sentences, and mistakes exactly as heard. Do not correct,
   translate, or clean up the wording.
2. **`source_kind` must be `"field"`** for real collected statements (never
   `"demo"`).
3. **`manual_transcription_attested` must be `true`.** This is only valid if
   you personally listened and transcribed the statement yourself. A `"field"`
   record without this set to `true` will be rejected on import.
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
  "raw_text": "<exact transcribed statement>",
  "manual_transcription_attested": true,
  "collector_id": "<your name or initials>",
  "topics": ["commuting"],
  "created_at": "<ISO 8601 timestamp, e.g. 2026-09-10T14:30:00Z>"
}
```

## Target

10-15 statements per group, covering as many of the topics above as
naturally occur. Do not invent statements to fill a topic quota — only
record what was actually heard.
