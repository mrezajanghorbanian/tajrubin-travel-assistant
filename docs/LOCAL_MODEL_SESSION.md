# CORE-02: bounded conversation continuity

Run the existing local model as described in [CORE-01](LOCAL_MODEL_TURN.md), then:

```sh
python -X utf8 -m app.assistant.local_model_session
```

Enter a message per line. `/exit` ends the process; `/reset` clears its session.
`--format json` emits one compact result object per model call and is also usable
with piped UTF-8 input. There is no UI or persistent conversation store.

Each session owns an immutable transcript containing the literal user messages
and validated intake replies. Every request sends that transcript and the current
message to the existing local model. The prompt asks for cumulative understanding
and the next missing detail; it treats earlier assistant text as fallible and
only user messages as statements of preference. There is no extraction by new
handwritten language rules. The pending question is the last accepted model
question. Concurrent sends/resets on an instance serialize, and different instances
have no shared history. Provider objects can be shared by controlled tests; their
own diagnostics/logging are outside this in-process memory boundary.

A valid response commits the turn atomically. Invalid input, malformed output,
provider failure or full capacity leaves the transcript unchanged. There is no
silent retry, fallback, truncation, summarization or disk write. The same loopback,
proxy, JSON Schema and local-validation controls as CORE-01 apply.

The deliberately small checkpoint allows at most four successful turns and a
2000-character serialized input context, including earlier replies. Each message
is 3–2000 characters, and `send` accepts an output budget of 128–1024 tokens
(default 256). Either bound may be reached first. Character bounds are not a
model-specific token guarantee: a smaller server context can still reject a
request. The CLI reports the limit and retains the old session until an explicit
reset; it never drops older facts to continue. EOF and `/exit` close the provider;
exit status is 1 if any model/input/limit error occurred during the process.

## Acceptance boundary

Literal facts (destination, dates, party, budget and preferences) survive in the
transcript. Their cumulative interpretation is model-generated, provisional text,
not a verified structured trip or deterministic semantic guarantee. No selected
plan exists yet. Typed trip-state reconciliation, grounded tools, initial planning
and partial edits remain open. This is a CORE-02 checkpoint, not full acceptance
of CORE-02–05 or a travel-quality benchmark.

CI uses synthetic stub responses to check continuity, isolation, reset, immutable
snapshots, bounds, failure rollback, retries and the multiline CLI. Real local
inference is recorded separately; contract tests alone do not prove understanding.

## Recorded real inference: 2026-11-03

[Raw synthetic-input evidence](evidence/core02-local-session-2026-11-03.json)
records three actual calls through `LocalModelSession.send`, using the same
session instance and the existing `qwen3.5-4b` server label, CPU mode, context
2048 and output budget 256. The server/model were restarted after the initial
health check reported connection refused; no model was downloaded.

| Turn | Synthetic user detail | Observed result | Seconds |
| --- | --- | --- | --- |
| 1 | Three relaxed, low-cost days in Shiraz | Preserved destination/duration/preferences; asked dates | 40.16 |
| 2 | From 20 Aban 1405, two travelers | Preserved prior details; added date and party; question null | 35.41 |
| 3 | Total budget ten million tomans, retain Shiraz | Preserved all prior details and added explicit budget; question null | 42.72 |

All three replies passed the strict intake contract. The interpretation was
manually compared to these synthetic messages; this is a narrow continuity
observation, not a general semantic guarantee. A null pending question does not
establish complete requirements, feasibility or a completed plan. No prices,
hours, attractions, calendar conversion or booking facts were inferred. The
model label is server-declared, not weight attestation. Separate-session
isolation, failure recovery and CLI behavior have regression evidence, not a
real-model multi-user quality benchmark.

## Optional grounded mode

Add `--grounded` to enable [CORE-03 local knowledge search](GROUNDED_SESSION.md)
in the same session. The intake-only default described above is unchanged.
Source notes are returned outside the model context; no selected plan or
structured trip state is introduced.
