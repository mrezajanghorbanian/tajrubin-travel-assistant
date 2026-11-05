"""Explicit confirmation -> conservative normalization -> existing signed preview.

The model cannot choose a runner or provide scheduling evidence. User statements
remain distinct from normalized inputs and from evidence-backed feasibility.
"""
from typing import Callable, Literal
from pydantic import Field

from app.assistant.local_model_turn import _Frozen
from app.assistant.trip_state import TripStateV1
from app.assistant.traveler_intent import TravelerIntentV1, _CITY_ALIASES, _DAY_REGEX, _count_values, _normalize, _PARTY_REGEX
from app.assistant.traveler_intent_v2 import TravelerIntentV2, analyze_traveler_intent_v2
from app.assistant.planning_readiness import PlanningReadinessV1, assess_planning_readiness
from app.assistant.trip_preview import TripPreviewV1, preview_trip_readiness


class PlanningBlockerV1(_Frozen):
    field: Literal['destination', 'duration', 'dates', 'party', 'budget', 'preferences', 'evidence']
    reason: str = Field(min_length=1, max_length=300)


class SessionPlanningV1(_Frozen):
    kind: Literal['planning_preview'] = 'planning_preview'
    status: Literal['needs_details', 'needs_validation', 'blocked', 'infeasible', 'provisional', 'unavailable']
    feedback: str
    question: str | None = None
    statements: TripStateV1
    blockers: tuple[PlanningBlockerV1, ...] = ()
    readiness: PlanningReadinessV1 | None = None
    preview: TripPreviewV1 | None = None
    live_verified: Literal[False] = False
    needs_verification: Literal[True] = True


PreviewRunner = Callable[[PlanningReadinessV1], TripPreviewV1]


def _parse(value: str):
    # Reuse existing bounded extraction; this is validation, not model output.
    return analyze_traveler_intent_v2('Plan a trip. ' + value)


def confirm_and_preview(state: TripStateV1, *, runner: PreviewRunner = preview_trip_readiness) -> SessionPlanningV1:
    """Called only by explicit application confirmation; never from model JSON.

    Runner injection is a trusted host/test configuration, not a user tool input.
    The default has no catalog, selections, network or scheduling assumptions.
    """
    missing = tuple(name for name in ('destination', 'dates', 'duration', 'party') if getattr(state, name) is None)
    if missing:
        return SessionPlanningV1(status='needs_details', statements=state,
            feedback='برای پیش‌نمایش، جزئیات اولیه سفر هنوز کامل نیست.',
            blockers=tuple(PlanningBlockerV1(field=name, reason='مقدار مشخص نشده است.') for name in missing))
    blockers = []
    def block(field, reason):
        blockers.append(PlanningBlockerV1(field=field, reason=reason))
    destination = _parse(state.destination.value)
    duration = _parse(state.duration.value)
    dates = _parse(state.dates.value)
    exact_destination = any(_normalize(state.destination.value) == _normalize(alias)
                            for _, aliases in _CITY_ALIASES for alias in aliases)
    if len(destination.destinations) != 1 or destination.origin is not None or not exact_destination:
        block('destination', 'در این مرحله یک مقصد پشتیبانی‌شده لازم است.')
    if duration.base.duration_days is None or 'duration_days' in duration.unresolved_fields or _DAY_REGEX.fullmatch(_normalize(state.duration.value)) is None:
        block('duration', 'مدت باید یک تعداد روز روشن و بین ۱ تا ۳۰ باشد.')
    exact_dates = False
    if dates.travel_dates is not None:
        start = dates.travel_dates.start_date.isoformat()
        allowed_dates = {start}
        if dates.travel_dates.end_date is not None:
            end = dates.travel_dates.end_date.isoformat()
            allowed_dates = {f'{start} to {end}', f'{start} تا {end}'}
        exact_dates = _normalize(state.dates.value) in {_normalize(value) for value in allowed_dates}
    if dates.travel_dates is None or 'travel_dates' in dates.unresolved_fields or not exact_dates:
        block('dates', 'تاریخ دقیق میلادی با قالب YYYY-MM-DD لازم است؛ تقویم یا تاریخ حدس زده نمی‌شود.')
    party_values = _count_values(_normalize(state.party.value), _PARTY_REGEX)
    party = next(iter(party_values)) if len(party_values) == 1 else None
    if party is None or not 1 <= party <= 30 or _PARTY_REGEX.fullmatch(_normalize(state.party.value)) is None:
        block('party', 'تعداد مسافران باید یک مقدار روشن بین ۱ تا ۳۰ باشد.')
    if state.budget is not None:
        block('budget', 'برای بررسی سقف بودجه، شواهد هزینه لازم است؛ بودجه بیان‌شده حذف یا رعایت‌شده فرض نمی‌شود.')
    if state.preferences is not None:
        block('preferences', 'ترجیح ثبت‌شده هنوز به قید قابل بررسی برنامه تبدیل نشده است؛ نیازمند تطبیق است.')
    if blockers:
        return SessionPlanningV1(status='needs_validation', statements=state, blockers=tuple(blockers),
            feedback='اطلاعات نقل‌شده هنوز برای ورودی برنامه‌ریز قابل اعتبارسنجی نیست.', question=blockers[0].reason)
    raw = '\n'.join(f'{name}: {getattr(state, name).value}' for name in TripStateV1.model_fields if getattr(state, name))
    base = TravelerIntentV1(request='Plan a trip.\n' + raw, intent_type='trip_planning',
        destination=destination.destinations[0], duration_days=duration.base.duration_days, party_size=party,
)
    intent = TravelerIntentV2(base=base, destinations=destination.destinations,
        travel_dates=dates.travel_dates)
    readiness = assess_planning_readiness(intent)
    if readiness.status != 'ready_for_draft':
        return SessionPlanningV1(status='needs_validation', statements=state, readiness=readiness,
            feedback='مدت و تاریخ یا قیود سفر نیازمند رفع ابهام هستند.', question=readiness.clarification_question)
    try:
        preview = runner(readiness)
    except (ValueError, OSError):
        return SessionPlanningV1(status='unavailable', statements=state, readiness=readiness,
            feedback='ابزار پیش‌نمایش در دسترس نیست؛ برنامه‌ای ثبت نشد.')
    if preview.readiness != readiness or (preview.status == 'provisional' and (preview.schedule is None or preview.schedule.status != 'provisional' or not preview.schedule.days)):
        return SessionPlanningV1(status='unavailable', statements=state, readiness=readiness,
            feedback='خروجی ابزار پیش‌نمایش با ورودی جاری سازگار نیست؛ برنامه‌ای ثبت نشد.')
    if preview.status in {'provisional', 'infeasible', 'blocked'}:
        status = preview.status
    else:
        status = 'blocked'
    feedback = {
        'needs_activity_selection': 'مکان‌های مستند برای روزهای سفر هنوز انتخاب نشده‌اند؛ برنامه‌ای ساخته نشد.',
        'needs_source_release': 'داده تأییدشده و امضاشده برای ساعات بازدید و مکان‌ها موجود نیست.',
        'evidence_rejected': 'شواهد مکان‌ها نامعتبر، قدیمی یا در دسترس نیستند؛ برنامه‌ای ساخته نشد.',
        'invalid_selection': 'انتخاب مکان یا تاریخ آن با جزئیات سفر سازگار نیست.',
        'provisional': 'پیش‌نمایش صرفاً بر اساس شواهد ارائه‌شده ساخته شد؛ اطلاعات زنده و رزرو تأیید نشده‌اند.',
    }.get(preview.status, 'برنامه با شواهد و محدودیت‌های فعلی قابل تکمیل نیست.')
    return SessionPlanningV1(status=status, statements=state, readiness=readiness, preview=preview,
        feedback=feedback, blockers=() if status=='provisional' else (PlanningBlockerV1(field='evidence',reason=feedback),))
