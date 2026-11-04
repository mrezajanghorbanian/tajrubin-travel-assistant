# CORE-04: same-session confirmation and planning preview

Run the existing `python -X utf8 -m app.assistant.local_model_session --trip-state`
conversation. Review the literal values displayed by the application, then enter
`/confirm`. In JSON mode this emits a distinct `kind: planning_preview` object;
it is application output, not another model reply. `/confirm` makes no inference,
does not consume a conversation turn and does not authorize booking or payment.

The library equivalent is `session.confirm_trip()`. It is available only in
trip-state mode. It reads the immutable **current** statement slots, never the
full old transcript. Correcting a duration therefore cannot silently bring an
older value back into planning. Provenance is retained in `statements`.

## Validation and outcomes

The bridge reuses existing conservative intent/readiness validation. It adds
whole-statement acceptance checks, rather than accepting a regex match from
inside a negation or range. Supported inputs at this checkpoint are one reviewed
city alias, one duration/count with a unit, and an exact Gregorian ISO date or
an ISO range joined by `to` / `تا`. Persian digits in supported numeric forms
are normalized by existing helpers. A Persian-calendar date is not converted
or reinterpreted as Gregorian. No calendar dependency or paid API is installed.

Party and duration counts must be unambiguous, within 1–30, and consume their
whole statement. Existing date-range/duration conflict checks still run. Strings
such as `not 3 days`, `31 or 2 people` or `not Tehran` cannot become confirmed
numeric/destination inputs just because an internal token matches.

Explicit budget and preference statements currently block the bridge: the
scheduler does not enforce costs or arbitrary pace/accessibility preferences.
They remain visible with their source messages and are never dropped or declared
satisfied. Even a supported numeric budget requires missing cost evidence. This
is deliberately narrower than general Persian interpretation, and confirmation
does not override an unsupported or unverified constraint.

| Status | Meaning |
| --- | --- |
| `needs_details` | Required statement slots are absent |
| `needs_validation` | Statements/constraints cannot be safely normalized or conflict |
| `blocked` | Normalized inputs lack activity selection or usable evidence, or scheduler blocks |
| `infeasible` | Existing scheduler rejects supplied constraints |
| `provisional` | The existing signed-catalog/evidence path produced a provisional schedule |
| `unavailable` | Known tool failure or mismatched preview; no schedule accepted |

The normal CLI has no preselected activities, catalog, signing keys, visit hours
or travel-time inputs. It therefore cannot produce a feasible travel plan from
a destination alone. It returns explicit missing-selection/evidence results.
Normalized readiness is draft input, not a completed itinerary.

`preview_trip_readiness` factors the existing request-to-preview composition so
the session can supply already assessed inputs without reparsing a fabricated
combined request. The legacy `preview_trip_request(text, ...)` delegates to it
and retains the same signed-release, approval, dated selection and scheduler
gates. There is no parallel unsigned scheduling path.

A trusted host may configure `preview_runner` to supply explicit selections,
signed releases, verification keys and directed travel evidence through that
same existing function. This is dependency injection for host integration/tests,
not a callable, file path, key or tool name accepted from model/user JSON. No
catalog/release fixture is installed into the normal runtime.

## State and error handling

`session.planning_preview` exposes the last immutable preview. Every accepted
new chat turn invalidates it, even if the literal values did not change. This
conservative invalidation prevents a stale schedule surviving a new constraint;
partial itinerary editing is not implemented. Failed/rejected turns preserve the
previous state and preview. Reset clears both, and separate sessions share neither.

Validation feedback becomes an application planning question in the next model
context, separately from model prose. No catalog/source text or schedule evidence
is fed to the model as instructions. Fixing a statement requires another explicit
confirmation before previewing again. Known tool errors are sanitized; returned
previews must refer to the current assessed input. A `provisional` label with no
actual provisional schedule is rejected.

The CLI exits 1 for unavailable tools or invalid command mode. A truthful blocked
or needs-validation preview is a handled result (exit 0), not a travel-quality PASS.
Model timeout/input/context failures retain the existing behavior and limits.

## Regression evaluation

Run `python -m pytest tests/test_session_planning.py tests/test_trip_preview.py -q`.
Tests cover explicit confirmation, current-state corrections, stale-preview
invalidation, source preservation, failure/reset/isolation, unsupported calendars,
ambiguous/out-of-range counts, duration/date conflicts, budget/preference retention,
partial-match rejection, tool-output mismatch, CLI behavior and a signed synthetic
catalog flowing through editorial review, release verification and the actual
scheduler. Revoking that fixture source rejects its next preview.

The controlled fixture uses a synthetic clock/date and an ephemeral test signing
key, not current travel facts or a private/user key. Positive fixture evidence is
separate from actual local-model/CLI evidence. This is a bridge checkpoint;
CORE-02 semantic confirmation, model-driven activity selection/recommendations,
full CORE-04 coverage and CORE-05 partial edits remain open.

## Recorded application evidence: 2026-11-05

[Actual local-model/CLI evidence](evidence/session-planning-real-2026-11-05.json)
uses the existing `qwen3.5-4b` model label, explicitly loaded with CPU / context
2048, the default 256-token output budget and 120-second ceiling. The actual CLI
subprocess handled two synthetic Persian requests, with `/reset` between cases:

- One day in Tehran, two travelers, `2026-11-20`: model extraction took 49.30s.
  `/confirm` normalized the current slots but returned `blocked` /
  `needs_activity_selection`, with no schedule or invented logistics.
- Same trip with `۲۰ آبان ۱۴۰۵`: model extraction took 38.09s. `/confirm`
  returned `needs_validation` on dates and preserved the literal calendar phrase.
  No Gregorian date was inferred. Both confirmations took under the recorded
  0.01s rounding resolution; the subprocess exited 0 with no stderr.

These are narrow, synthetic-input observations, not a general Persian/calendar
benchmark or evidence that a live trip can be completed.

[Separate signed-fixture evidence](evidence/session-planning-fixture-2026-11-05.json)
uses a synthetic provider, not real model inference. A reviewed, ephemeral-key
signed `synthetic.gallery` selection flowed from the **same session** through
confirmation, release verification and the existing scheduler. The controlled
visit ran 09:00–10:00 with knowledge/source IDs, then revoking the source made
the next preview `evidence_rejected` with no schedule. The fixture clock is
2026-10-26 and its visit date is 2026-11-03; those are test inputs, not the actual
execution date or current attraction facts. No private signing material is in
the evidence. Only the positive fixture has enough scheduling evidence; no real
traveler itinerary is claimed.
