# Unified offline assistant entry point

One command now composes the existing request parser, planning-readiness gate
and source-attributed knowledge answers. It uses the project's Python package
and base dependencies, with no model, provider, signing runtime or network calls.

## Run

```sh
python -X utf8 -m app.assistant 'کاخ گلستان' --city تهران --country IR
python -X utf8 -m app.assistant 'برای تهران برنامه سفر میخواهم'
python -X utf8 -m app.assistant 'برای ۳ روز تهران برنامه سفر میخواهم' --format json
python -X utf8 -m app.assistant 'Plan a 3 day trip' --format json
```

The first command returns the local summary and its official source URL.
The second asks for the trip duration in Persian. The third returns parsed
draft inputs with `logistics_verified=false`. The fourth asks for a destination.
The default output is readable text; `--format json` returns the typed envelope.

## Bounded behavior

| Request path | Result | Evidence boundary |
| --- | --- | --- |
| Knowledge question | `kind=knowledge_answer` with a provisional answer or explicit insufficient evidence | Load the local Markdown pack; retain IDs, source URLs and review dates |
| Planning request with missing or conflicting facts | `kind=planning_readiness`, `status=needs_clarification` | Ask the existing parser's highest-priority clarification |
| Planning request with resolved initial facts | `kind=planning_readiness`, `status=ready_for_draft` | Return draft inputs; dated attraction and travel-time evidence remains required |

The envelope always has `live_verified=false` and `needs_verification=true`.
Its contract requires exactly one matching payload, either `knowledge` or
`planning`. A `not_planning` readiness result cannot be presented as the
planning response branch.

The new entry point enables the reviewed Persian/English retrieval equivalents.
The older `app.assistant.demo` command retains its existing opt-in flag and
default lexical behavior. Knowledge filters `--country` and `--city` and the
`--max-results` bound of 1–5 are preserved. Supplying city/country filters with
a planning request returns an input error; destinations belong in that request's
text so hard constraints are not silently discarded or inferred from QA filters.

Planning readiness does not load the knowledge pack. An unavailable pack blocks
the question path while initial planning clarification remains usable. Invalid
requests or inputs exit 2 with a bounded error message; successful knowledge
abstention exits 0. The interface stores no conversation state.

## Python boundary

```python
from app.assistant.entrypoint import handle_local_request
from app.assistant.grounded_qa import TravelQuestionV1

result = handle_local_request(TravelQuestionV1(question="کاخ گلستان", city="تهران"))
print(result.model_dump_json(indent=2))
```

`handle_local_request` reuses `TravelQuestionV1` for bounded input and returns
`LocalAssistantResponseV1`. `knowledge_root` can select a local pack for
knowledge requests. Existing loader checks for duplicate IDs, invalid records
and symlinked source files remain in force.

## Implementation choice and limits

This slice calls the existing Python components directly and adds an exclusive
response envelope. This preserves their validation and evidence policies without
introducing subprocess orchestration or another reasoning engine. The routing
uses the existing conservative rule-based intent classification, including its
known limits for ambiguous wording and unsupported locations. Broad destination
recommendation requests may still receive insufficient evidence.

Resolved draft inputs do not contain a visit schedule, selected attractions,
verified hours, routes or bookings. [Trip-preview evidence requirements](TRIP_PREVIEW.md)
remain separate. Replies use stored summaries; the entry point does not generate
translations, invent live details or maintain a multi-turn dialogue.

## Validation

```sh
python -m pytest tests/test_local_assistant_entrypoint.py -q
python -m pytest tests -q
```

Tests exercise the real module in both languages, public source propagation,
unsupported queries, conflicting dates, missing fields, filter rejection,
result bounds, missing packs and the exclusive response contract. A separate
child process blocks provider/signing imports and exercises both paths.

Local validation: 508 passed, 1 Windows symlink skip; all 28 new entry-point tests passed. Both frozen retrieval gates, the repository security gate, Bandit and pip dependency consistency check passed.
