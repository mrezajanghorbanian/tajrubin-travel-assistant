# CORE-02: source-backed trip statements in the same conversation

```sh
python -X utf8 -m app.assistant.local_model_session --trip-state
```

This opt-in mode extends the existing session and enables its grounded search
path. It does not create a second session store. `--format json` exposes the
structured result. Intake-only and `--grounded` behavior remain unchanged.

## Stored state and provenance

Six named slots preserve literal user statements: `destination`, `duration`,
`dates`, `party`, `budget`, and `preferences`. Each is null or an immutable
`{value, source_turn}` record. The value is a nonblank string of at most 200
characters. The application assigns the 1-based accepted message number; the
model cannot choose or rewrite provenance. Unset slots remain null.

These are typed, attributed statements, not verified/normalized trip facts.
For example, `سه روز`, a Persian date or `ده میلیون تومان` remains the user's
literal phrase. The code does not infer ISO dates, numeric party sizes, currency
conversions or feasibility. Existing planner intent/evidence validation must
still run before these statements can become scheduling inputs.

The model receives the current snapshot with the prior conversation and returns
`updates`, an object with all six keys required. Each value is a literal excerpt
from **current_user** or null, meaning no change. Every non-null value must occur
exactly in that message. Previous user messages, assistant summaries, knowledge
notes and model guesses cannot supply fresh update evidence. No translation or
number normalization is silently accepted. Duplicate JSON keys, missing/unknown
slot keys, wrong types and oversized values are rejected.

Application code merges only supplied updates. Missing/null values never erase
previous slots, and an accepted correction replaces only the named slot and its
source message. This preserves unrelated fields even if the model's prose omits
them. Slots contain scalar statements: updating `preferences` replaces that
whole slot, not individual preferences inside its text. Selective deletion and
list editing are not implemented; `/reset` explicitly clears the entire session.

Literal anchoring is not semantic verification. A model may omit a detail,
misclassify a quotation, negation or uncertain range, or put an irrelevant literal
phrase into a slot. The prompt asks for clarification on ambiguity; application
schema validation alone does not prove that the model follows this instruction.
Nothing in this checkpoint marks a trip ready or a user statement confirmed.

## Atomicity and outcomes

State updates are staged before the knowledge tool. If any excerpt is unanchored,
no tool runs and neither state nor conversation advances. A provider/contract
failure, tool rejection, knowledge-load failure or capacity limit also commits
neither state nor transcript. Successful no-evidence retrieval is a completed
tool operation and can commit the user's literal statements.

A state-enabled result adds the immutable `trip_state` snapshot and:

| `state_status` | Meaning |
| --- | --- |
| `applied` | Accepted turn with at least one literal update |
| `unchanged` | Accepted turn with six null updates |
| `rejected` | An update was not present in the current message; no tool executed |
| `not_applied` | Model or tool failed; prior state returned |

`applied` establishes contract/provenance acceptance, not semantic correctness.
Text mode displays Persian slot labels and source-message numbers; JSON mode
retains schema field names. A rejected state update makes the CLI exit 1.

All state is in-process only. Session reset, isolation, locking and immutable
snapshot behavior include typed state. The existing four-turn / 2000-character
serialized input bounds remain, including state metadata; they can be reached
sooner in this mode. No silent truncation, disk storage or paid provider is added.

## Evaluation and remaining work

Regression tests use synthetic model patches to check all six slots, budget-only
correction, provenance, missing/null handling, immutable snapshots, isolation,
reset, duplicate/missing/unknown keys, invented or replayed values, partial-merge
rollback, model/tool failures, knowledge integration, capacity and CLI behavior.
Real-model observations are recorded separately below. Fixture tests prove the
merge controls, not reliable Persian extraction or general travel quality.

Selected-plan state, semantic reconciliation and confirmation, normalized planner
inputs, CORE-04 initial planning and CORE-05 partial itinerary edits remain open.

## Recorded real inference: 2026-11-03

[Evidence](evidence/trip-state-session-2026-11-03.json) records three consecutive
synthetic-input calls in one actual session using the existing local
`qwen3.5-4b` server label, CPU configuration, context 2048 and output budget 512:

1. `برای سه روز شیراز یه سفر آرام می‌خوام.` produced destination `شیراز`,
   duration `سه روز` and preference `آرام`, each sourced to message 1 (53.12s).
2. The follow-up supplied 20 Aban 1405, two travelers and ten million tomans.
   All six slots were present after application merging; new values referenced
   message 2 and previous values still referenced message 1 (57.22s).
3. A budget-only correction to fifteen million tomans changed exactly that slot
   and its source to message 3. All five other slot records remained identical,
   even though the model's prose only summarized the budget change (50.05s).

An actual `--trip-state --format json` CLI subprocess, using its default 256-token
budget, also extracted the three initial slots and exited 0 with no stderr
(36.38s). No stub responses were used in these observations. All timings are
local observations, not performance claims, and the model label is server-declared.

The earlier variable-length update-list design failed the real extraction check:
its first reply captured duration but omitted explicit destination and pace. The
raw first reply is retained in the evidence. Before publication the schema was
changed to six required nullable keys, with a short extraction example. Negative
schema/provenance tests remain strict, including rejection of duplicate JSON keys.

The final check uses a known example pattern and a narrow conversation. It is not
an independent model benchmark. The first real reply did not ask for missing
dates; the synthetic follow-up supplied them without a question. Thus clarification
quality and complete conversational acceptance remain open. The result proves
this observed extraction/correction sequence plus application preservation controls,
not general semantic reliability, normalized dates or a feasible travel plan.

## Required-details follow-up policy

In `--trip-state` mode an accepted turn now includes `follow_up` with `status`,
`missing_fields`, `question`, `source` and `requested_field`. A deterministic
application policy checks presence of destination, dates, duration and party,
in that priority order. Budget and preferences remain optional at this gate.
These are presence checks over the typed slots, not new natural-language parsers.

If the valid model reply already contains a clarification question, it is retained
with source `model`. Otherwise, the application asks for the first missing required
field, with source `application_policy`. This explicitly handles the earlier real
model's null question without rewriting its text: `intake.clarification_question`
remains the original model value. No policy runs as a substitute for failed model
inference, invalid patches or failed tools. There is no extra inference or retry.

The session's effective pending question includes the accepted application question.
History sends it back as `application_question`, outside the model's prior assistant
intake. This preserves provenance and lets the next model call interpret the user's
answer. CLI text prints one effective question; JSON reports its source explicitly.
The original intake-only and grounded-only modes keep their question behavior.

`needs_details` means required slots are missing. Once they are present, the status
is `needs_validation`, never ready, feasible or complete. A literal phrase such as
an incomplete date can occupy a slot without being a usable date; normalization,
semantic confirmation, conflicting updates and itinerary evidence still need work.
A model-supplied question may itself be irrelevant or repetitive; this policy does
not classify its meaning or guarantee general clarification quality.

The policy is recomputed after each successful state merge, so a supplied date
is removed from the missing-field list. A failed call cannot change the effective
question, state or transcript. Reset and per-session isolation include this question.
A successful no-evidence knowledge search can still ask for missing trip details.

### Real CLI follow-up evidence: 2026-11-03

[Evidence](evidence/trip-follow-up-2026-11-03.json) records an actual two-turn
`--trip-state --format json` subprocess with the existing local `qwen3.5-4b`
server label, default 256 output tokens and unchanged 120-second request timeout.
After explicitly reloading that installed model with `--gpu off` and context
2048 (no download), the synthetic conversation completed:

1. Three relaxed days in Shiraz: the model's question was null; the application
   separately asked for travel dates, with source `application_policy` (56.69s).
2. Reply with 20 Aban 1405 and two travelers: those literal slots were recorded
   with source message 2; destination/duration/pace and their provenance survived.
   The effective question cleared and status became `needs_validation` (46.39s).

The subprocess exited 0 with empty stderr. No mock model responses were used.
This establishes the narrow observed follow-up path, not general date parsing,
clarification quality or trip completion. The known example pattern and local
latencies are not an independent benchmark.

Earlier attempts remain in the evidence: an initial timeout (~122s including
process overhead), followed by a retry under an observed 4096 context that asked
for dates but timed out on the answer (~111s / 120s). Failed turns returned no
follow-up and did not commit new state. The model was then reloaded with the CPU
configuration above. These observations do not isolate GPU/context/load as the
cause, and runtime variability remains open. The application deadline was not
extended and no automatic retry or rule-only substitute for failed inference was
introduced.
