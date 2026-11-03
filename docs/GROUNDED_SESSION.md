# CORE-03: model-selected local knowledge search

```sh
python -X utf8 -m app.assistant.local_model_session --grounded
```

This extends the same [CORE-02 session](LOCAL_MODEL_SESSION.md), rather than
introducing another conversation store. The existing default intake mode and
CORE-01 command remain unchanged. Add `--format json` for structured output.
There is no download, paid API, network search, booking adapter or runtime harness.

## Execution contract

One local-model call returns cumulative intake plus `search`: null or exactly
`{query, city}`. A search and a clarification question cannot coexist. The server
receives a strict JSON Schema; local validation rejects unknown fields, missing
fields, duplicate keys, invalid types and oversized output. Only application
code selects the fixed `complete_knowledge_step` executor. Model text cannot
select a function name, file path, URL, country, result count or shell command.

Query (3–300 characters) and city (1–120) must each appear literally in a user
message from the same session, case-insensitively. Earlier assistant text cannot
supply either argument. This conservative checkpoint rejects invented city/query
strings, including translated arguments absent from user messages. Existing
bilingual retrieval handles reviewed Persian/English equivalents instead.
Literal occurrence is not a proof that the model understood a correction,
negation or city correctly; those semantic limits remain visible.

The tool always loads the repository's fixed public knowledge pack and applies
the requested city plus country `IR`, up to three hits, with reviewed bilingual
aliases. There is no fallback to another city. Only documents with review-date
metadata and an HTTPS source reference are eligible; these metadata checks do
not certify freshness or accuracy. The older unattributed Tehran overview is
excluded from this tool, while the original deterministic QA mode is unchanged.

The application returns original document summaries, IDs, external source URLs
and review dates through the existing provisional QA renderer. The model never
writes citations or an answer based on retrieved text: there is no second model
call. Raw summaries are labelled source notes in text mode and remain untrusted
data. They cannot authorize another tool call and never enter subsequent model
context. Therefore source prompt injection has no execution path here; the
source text can still contain inaccurate or malicious prose and requires review.
This checkpoint is attributed retrieval, not model-written recommendations.

## Outcomes and state

The existing model envelope is extended with:

| `tool_status` | Meaning | Session commit |
| --- | --- | --- |
| `not_requested` | Clarification/intake or failed model call; no search executed | Only a valid intake commits |
| `completed` | Search executed; `knowledge` is provisional or explicitly insufficient | Yes |
| `rejected` | Valid JSON, but arguments are not anchored in user messages | No |
| `unavailable` | Pack load/retrieval failed; no raw diagnostics returned | No |

`knowledge_request` is present for attempted searches and `knowledge` only for
completed ones. A knowledge gap is a successful tool result, not a service error.
A tool/model failure preserves the prior transcript so a retry remains possible.
The CLI exits 1 if a service/contract/tool/limit/input error occurred, while an
explicit no-evidence search is exit 0. The pending question still comes from
accepted intake; no retrieved source or selection is promoted into trip state.

The four-turn / 2000-character serialized context limits remain. The CLI output
budget remains 256; `send(..., max_tokens=384)` can be used for controlled checks.
Character limits do not guarantee fit within every local server's token context.

## Evaluation

Regression tests execute real local retrieval with synthetic model decisions:
Persian/English Golestan queries, absent/unknown cities, unanchored queries,
unknown action fields, conflicting steps, missing sources/review dates, injected
source instructions, pack failure/retry, same-session follow-ups and text/JSON
CLI behavior. Existing retrieval development gates remain unchanged. These tests
prove bounded application behavior, not general model or travel quality.

CORE-02 typed trip-state reconciliation and selected-plan state, CORE-03 broader
recommendation quality, CORE-04 planning and CORE-05 edits remain open. No live
hours, prices, availability or booking facts are supplied by this connection.

## Recorded real inference: 2026-11-03

[Evidence](evidence/core03-grounded-session-2026-11-03.json) records two
consecutive calls in one grounded session against the existing local
`qwen3.5-4b` server label (CPU, context 2048, output budget 384):

1. Persian request for a relaxed three-day Shiraz trip and destination information:
   model chose city/query `شیراز`; actual retrieval returned explicit insufficient
   evidence, without substituting Tehran (35.58s).
2. The same synthetic traveler changed the request to Golestan Palace in Tehran:
   model chose an anchored Tehran query; actual retrieval returned
   `ir.tehran.golestan-palace`, the UNESCO reference and review date 2026-10-29
   (31.78s). These are stored metadata; the external page was not fetched or
   revalidated during the test.

A separate actual CLI subprocess using `--grounded --format json`, its default
256-token budget and a Golestan request returned the same attributed record,
exit 0, with no stderr (23.00s). No stub responses were used in these three
observations. The model label is server-declared, not weight attestation.

This shows one no-evidence path, one changed-city follow-up and the CLI source
path. It does not establish general recommendation quality or reliable retention
of every trip slot: the second model summary focuses on the new request rather
than repeating the earlier duration/pace. Literal messages remain in session,
while structured semantic reconciliation remains unfinished. Timing is local
observation, not a benchmark. All messages are synthetic; no personal data,
private repository or paid service was used.
