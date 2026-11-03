# Product direction: Persian-first conversational travel agent

Owner clarification recorded: 2026-11-03. This is the execution priority for
closing the existing Trip Planner flow, not a claim that it is implemented.

## تعریف محصول

تجربین یک ایجنت سفر با رابط چت است: کاربر هدفش را با زبان طبیعی فارسی
بیان می‌کند و ایجنت با حفظ زمینه مکالمه، اطلاعات مستند و ابزارهای مشخص،
کار سفر را مرحله‌به‌مرحله پیش می‌برد. کاربر نباید برای استفاده از محصول،
دستورهای فنی، قراردادهای داده یا پرامپت‌نویسی بلد باشد.

تمرکز مرحله اول، سفرهای داخل ایران و کاربران فارسی‌زبان است. سفرهای خارجی
در مرحله بعد با داده و اتصال مناسب هر مقصد گسترش می‌یابند. پشتیبانی فنی
انگلیسی و آزمون‌های دوزبانه حفظ می‌شوند، اما معیار اصلی تجربه اولیه،
مکالمه طبیعی فارسی است.

مدل محلی موجود باید فهم درخواست، پرسش ضروری، انتخاب ابزار و تدوین پاسخ
را هدایت کند. اطلاعات مقصد از منابع و ابزارها می‌آید؛ کد نیز ورودی و
خروجی ابزار، صحت ارجاع‌ها و محدودیت‌های برنامه را بررسی می‌کند. قواعد
دستی باید برای کنترل‌های مشخص استفاده شوند، نه به‌عنوان جایگزین عمومی
فهم زبان طبیعی.

کاربر در ادامه همان چت بتواند بگوید «روز دوم سبک‌تر باشه» یا «این مکان رو
عوض کن» و ایجنت تصمیم‌های قبلی و بخش‌های دست‌نخورده سفر را حفظ کند.
هر اقدام اجرایی باید نتیجه روشن داشته باشد: انجام‌شده، ناموفق، یا منتظر
اطلاعات/تأیید. تا قبل از اتصال و تأیید تأمین‌کننده، رزرو انجام‌شده گزارش
نمی‌شود.

## Current implementation boundary

The repository contains a local model runtime configuration and a
provider-neutral generation adapter. The current `app.assistant` command
still runs deterministic QA/readiness paths; model-driven dialogue, tool
orchestration, session continuity and a complete editable trip are not yet
integrated. An installed/configured model and a successful agent workflow
are separate facts that require separate verification.

CORE-01 now has a separate [local-model intake entry point](LOCAL_MODEL_TURN.md)
with explicit failure states and strict JSON validation. It calls the existing
model adapter; the deterministic command is not silently rebranded as model
output. Real inference evidence and quality/runtime limitations are recorded
in that entry-point document. A bounded [in-memory conversation checkpoint](LOCAL_MODEL_SESSION.md) now
passes prior user turns and pending questions into subsequent local-model calls.
An opt-in [grounded search mode](GROUNDED_SESSION.md) now lets the model select
a bounded local knowledge read in that same session. Typed trip-state
semantic reconciliation and the complete CORE-02 through CORE-05 journey remain
open. [Literal trip-state slots](TRIP_STATE_SESSION.md) now preserve attributed
user statements and apply partial updates atomically in that same session. An
explicit required-detail policy now supplies a source-labelled application
question when a valid model reply omits one, without rewriting model text.
Required slot presence still leads to needs-validation, not a completed trip.

The existing scheduler and evidence checks are reusable execution tools.
Missing visitor hours, transfer times, durations or costs must remain explicit;
model-generated text does not turn them into verified facts. A blocked or
partial plan must not be presented as a feasible completed trip.

## Active sprint: close one conversational journey

Complete these stages in order before beginning booking or other new feature
implementation. This supersedes the earlier permission to run BOOK-02 in
parallel with core work.

| Stage | Deliverable | Completion evidence |
| --- | --- | --- |
| CORE-01 / existing local model | Connect the existing local provider to a bounded agent entry point; report actual model availability and failures | Real Persian inference through the application adapter, with model identity and bounded request recorded; no silent rule-only fallback presented as model output |
| CORE-02 / conversation state | Preserve explicit destination, dates, party, budget, preferences, pending questions and selected plan across turns | A Persian clarification turn updates the same session without losing or inventing prior facts; no cross-session leakage; no persistent personal memory by default |
| CORE-03 / grounded tools | Let the model invoke bounded, schema-validated retrieval/recommendation tools over available Iran knowledge | Relevant suggestions retain source IDs and freshness metadata; unsupported destinations or missing evidence are explained; untrusted source text cannot authorize tool actions |
| CORE-04 / initial trip | Compose selected places with the existing planning/evidence/scheduler boundaries | Either a source-attributed plan respecting supplied hard constraints, or an explicit partial/blocked result identifying missing evidence; no invented logistics |
| CORE-05 / edit in chat | Apply a requested change to part of the trip and recheck affected constraints | A Persian follow-up changes the intended day/stop while preserving unrelated accepted items; newly introduced conflicts remain visible |

These are implementation gates, not newly completed features. The first
deliverable is CORE-01 followed by the smallest connected CORE-02/03 journey;
do not replace it with more standalone parser rules or disconnected libraries.

CORE-01 progress: the bounded entry point and explicit failure handling are
implemented, with two [recorded real Persian single-turn checks](LOCAL_MODEL_TURN.md#recorded-real-inference-2026-11-03).
This establishes the first connection checkpoint. Model quality, latency and
runtime reliability remain limited evidence. CORE-02 now has bounded transcript
continuity, isolated sessions and atomic failure handling, plus opt-in typed
user-statement slots. Semantic confirmation, normalized planning inputs and
selected-plan state remain open. CORE-03 has a first attributed-retrieval checkpoint; model-written
recommendations and a connected editable plan remain open. Three [real consecutive Persian turns](LOCAL_MODEL_SESSION.md#recorded-real-inference-2026-11-03)
preserved and extended the same synthetic trip request. The complete
conversational acceptance journey remains open.

## Product acceptance conversation

Use a synthetic traveler conversation, not real personal data:

1. User: «برای سه روز شیراز یه سفر آروم می‌خوام.»
2. Agent retains the stated destination, duration and pace, asking only for
   necessary missing information before the next action.
3. User supplies that information; the agent updates the same trip/session.
4. Agent retrieves documented options. If local Shiraz coverage is absent,
   it explains that gap rather than fabricating attractions or switching city.
5. With a controlled, clearly synthetic sourced fixture covering the needed
   evidence, the agent builds the initial plan through the actual tools.
6. User: «روز دوم سبک‌تر باشه؛ مکان اول رو نگه دار.» The agent preserves the
   requested item, edits the relevant portion, and rechecks constraints.
7. An unavailable model/tool or insufficient evidence produces a truthful
   recoverable response, without claiming completion or starting a purchase.

Run both fixture-based regression tests and real local-model Persian sessions.
Record their evidence separately. CI mocks prove contract behavior, not model
quality; a model greeting proves connectivity, not the complete travel journey.
The core sprint closes only after this connected conversation works and its
remaining data limits are visible. Test count alone does not close it.

## Deferred expansion

[F-BOOK-01](BOOKING_INTEGRATION.md), including its offline adapters, remains
planned and deferred until CORE-01 through CORE-05 are accepted. Live flight,
hotel and experience search, checkout/booking and post-booking actions follow
their separate access, data and approval gates. Foreign-destination expansion
follows validated Iran-first behavior and destination-specific evidence.

Keep the public/private boundary, no-paid-service restriction, requested
branch and Draft PR policy in force. No private backend integration, model
replacement, paid service activation or autonomous purchase is authorized by
this product-direction document.
