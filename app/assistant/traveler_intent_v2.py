"""Travel intent v2: conservative route, ISO-date and budget extraction.

This extends (rather than modifies) the stable v1 contract. It operates
locally without a model, geocoding, currency conversion or live travel data.
"""
from __future__ import annotations

import argparse
import re
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.assistant.traveler_intent import (
    TravelerIntentV1,
    _CITY_ALIASES,
    _normalize,
    analyze_traveler_intent,
)

UnresolvedField = Literal["destinations", "duration_days", "travel_dates", "budget"]
CurrencyUnit = Literal["USD", "EUR", "IRR", "TOMAN"]

_CITY_TERMS = sorted(
    ((alias, city) for city, aliases in _CITY_ALIASES for alias in aliases),
    key=lambda item: (-len(item[0]), item[0]),
)
_CITY_PATTERN = "|".join(re.escape(alias) for alias, _ in _CITY_TERMS)
_CITY_MAP = {alias: city for alias, city in _CITY_TERMS}
_CITY_REGEX = re.compile(rf"(?<!\w)(?P<city>{_CITY_PATTERN})(?!\w)")
_ROUTE_ORIGIN = re.compile(
    rf"(?<!\w)(?:from|از)\s+(?P<origin>{_CITY_PATTERN})\s+"
    rf"(?:to|به)\s+(?P<destination>{_CITY_PATTERN})(?!\w)"
)
_DATE_REGEX = re.compile(r"(?<!\d)(?:19|20)\d{2}-\d{2}-\d{2}(?!\d)")
_OTHER_DATE = re.compile(
    r"(?<!\d)(?:1[34]\d{2}|20\d{2})[/-]\d{1,2}[/-]\d{1,2}(?!\d)"
)
_MONEY_NUMBER = r"(?:\d{1,3}(?:,\d{3})+|\d{1,12})(?:\.\d{1,2})?"
_MONEY_SCALE = r"(?:million|thousand|میلیون|هزار)"
_MONEY_UNIT = r"(?:usd|dollars?|eur|euros?|irr|rials?|tomans?|تومان|تومن|ریال|\$|€)"
_MONEY_REGEX = re.compile(
    rf"(?<!\w)(?:(?P<prefix>usd|eur|irr|dollars?|euros?|rials?|tomans?|تومان|تومن|ریال|\$|€)\s*)?"
    rf"(?P<amount>{_MONEY_NUMBER})\s*(?P<scale>{_MONEY_SCALE})?\s*"
    rf"(?P<suffix>{_MONEY_UNIT})?(?!\w)"
)
_BUDGET_CUE = re.compile(
    r"(?:\bbudget\b|\bcost\b|\bspend\b|\bunder\b|\bup to\b|بودجه|هزینه|حداکثر|سقف)"
)


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)


class TravelDatesV2(_StrictModel):
    start_date: date
    end_date: date | None = None


class TravelBudgetV2(_StrictModel):
    amount: Decimal = Field(gt=0, le=Decimal("1000000000000"))
    unit: CurrencyUnit
    original_expression: str = Field(min_length=1, max_length=100)


class TravelerIntentV2(_StrictModel):
    intent_version: Literal["2.0"] = "2.0"
    extraction_method: Literal["rule_based"] = "rule_based"
    base: TravelerIntentV1
    origin: str | None = None
    destinations: tuple[str, ...] = ()
    route_order_explicit: bool = False
    travel_dates: TravelDatesV2 | None = None
    budget: TravelBudgetV2 | None = None
    unresolved_fields: tuple[UnresolvedField, ...] = ()
    clarification_question: str | None = None


def _places(text: str) -> tuple[str | None, tuple[str, ...], bool]:
    positions: list[tuple[int, str]] = []
    for match in _CITY_REGEX.finditer(text):
        city = _CITY_MAP[match.group("city")]
        positions.append((match.start(), city))
    unique = tuple(dict.fromkeys(city for _, city in positions))
    origin: str | None = None
    explicit = False

    route = _ROUTE_ORIGIN.search(text)
    if route:
        origin = _CITY_MAP[route.group("origin")]
        destination = _CITY_MAP[route.group("destination")]
        # Origin is not automatically a visit stop.
        unique = tuple(c for c in unique if c != origin)
        if destination not in unique:
            unique = (destination,) + unique
        explicit = True
    elif len(unique) > 1:
        # A textual mention order is not proof of an intended visit order.
        explicit = re.search(r"(?:\bthen\b|سپس|بعد|(?<=\s)to(?=\s)|(?<=\s)به(?=\s))", text) is not None
    return origin, unique, explicit


def _travel_dates(text: str) -> tuple[TravelDatesV2 | None, bool]:
    matches = _DATE_REGEX.findall(text)
    other = _OTHER_DATE.findall(text)
    # Explicit Gregorian ISO dates only. Never guess the Jalali/Gregorian calendar.
    if any(value not in matches for value in other) or len(matches) > 2:
        return None, True
    if not matches:
        return None, False
    try:
        parsed = [date.fromisoformat(raw) for raw in matches]
    except ValueError:
        return None, True
    if len(parsed) == 2 and parsed[1] < parsed[0]:
        return None, True
    if len(parsed) == 2 and parsed[0] == parsed[1]:
        return TravelDatesV2(start_date=parsed[0], end_date=parsed[1]), False
    return TravelDatesV2(
        start_date=parsed[0],
        end_date=parsed[1] if len(parsed) == 2 else None,
    ), False


def _money_unit(raw: str) -> CurrencyUnit:
    if raw in {"usd", "dollar", "dollars", "$"}:
        return "USD"
    if raw in {"eur", "euro", "euros", "€"}:
        return "EUR"
    if raw in {"irr", "rial", "rials", "ریال"}:
        return "IRR"
    return "TOMAN"


def _budget(text: str) -> tuple[TravelBudgetV2 | None, bool]:
    amounts: list[TravelBudgetV2] = []
    seen_currency_mentions = 0
    for match in _MONEY_REGEX.finditer(text):
        prefix, suffix = match.group("prefix"), match.group("suffix")
        if not prefix and not suffix:
            continue
        seen_currency_mentions += 1
        if prefix and suffix and _money_unit(prefix) != _money_unit(suffix):
            return None, True
        local = text[max(0, match.start() - 70): min(len(text), match.end() + 30)]
        if not _BUDGET_CUE.search(local):
            # A museum ticket's price is not necessarily the travel budget.
            continue
        try:
            number = Decimal(match.group("amount").replace(",", ""))
            scale = match.group("scale")
            if scale in ("million", "میلیون"):
                number *= 1_000_000
            elif scale in ("thousand", "هزار"):
                number *= 1_000
            if not (0 < number <= Decimal("1000000000000")):
                return None, True
            amounts.append(
                TravelBudgetV2(
                    amount=number,
                    unit=_money_unit(prefix or suffix or ""),
                    original_expression=match.group().strip()[:100],
                )
            )
        except (InvalidOperation, ValueError):
            return None, True
    if not amounts:
        return None, False
    distinct = {(item.amount, item.unit) for item in amounts}
    if len(distinct) > 1:
        return None, True
    return amounts[0], False


def analyze_traveler_intent_v2(text: str) -> TravelerIntentV2:
    base = analyze_traveler_intent(text)
    normalized = _normalize(base.request)
    origin, destinations, order_explicit = _places(normalized)
    dates, ambiguous_dates = _travel_dates(normalized)
    budget, ambiguous_budget = _budget(normalized)

    unresolved: list[UnresolvedField] = []
    if base.intent_type == "trip_planning":
        if not destinations:
            unresolved.append("destinations")
        if base.duration_days is None and not (dates and dates.end_date):
            unresolved.append("duration_days")
    if ambiguous_dates:
        unresolved.append("travel_dates")
    if ambiguous_budget:
        unresolved.append("budget")

    persian = re.search(r"[\u0600-\u06ff]", base.request) is not None
    questions_fa = {
        "destinations": "برای کدام مقصد یا مقصدها برنامه سفر می‌خواهید؟",
        "duration_days": "سفرتان چند روز است؟",
        "travel_dates": "تاریخ سفر را با مشخص‌کردن تقویم و تاریخ دقیق می‌گویید؟",
        "budget": "بودجه سفر را با یک مبلغ و واحد پول مشخص می‌کنید؟",
    }
    questions_en = {
        "destinations": "Which destination or destinations are you visiting?",
        "duration_days": "How many days will you travel?",
        "travel_dates": "What are your exact travel dates and calendar?",
        "budget": "What is your budget amount and currency?",
    }
    question = (questions_fa if persian else questions_en)[unresolved[0]] if unresolved else None

    return TravelerIntentV2(
        base=base,
        origin=origin,
        destinations=destinations,
        route_order_explicit=order_explicit,
        travel_dates=dates,
        budget=budget,
        unresolved_fields=tuple(unresolved),
        clarification_question=question,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Travel request v2 (conservative extraction)")
    parser.add_argument("request", help="English or Persian travel request")
    args = parser.parse_args()
    print(analyze_traveler_intent_v2(args.request).model_dump_json(indent=2))


if __name__ == "__main__":
    main()


__all__ = [
    "TravelDatesV2", "TravelBudgetV2", "TravelerIntentV2",
    "analyze_traveler_intent_v2",
]
