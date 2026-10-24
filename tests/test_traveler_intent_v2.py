"""Travel intent v2 regression tests: no inferred data and backward compatibility."""
from datetime import date
from decimal import Decimal
from app.assistant.traveler_intent_v2 import analyze_traveler_intent_v2
from app.assistant.traveler_intent import analyze_traveler_intent


def test_multiple_destinations_preserve_mentions_without_inventing_route():
    x = analyze_traveler_intent_v2("Plan a 5 day trip to Tehran and Shiraz")
    assert x.destinations == ("Tehran", "Shiraz")
    assert x.route_order_explicit is False
    assert x.base.destination is None
    assert x.unresolved_fields == ()


def test_from_to_origin_is_not_a_visited_stop():
    x = analyze_traveler_intent_v2("Plan a 3 day trip from Tehran to Shiraz")
    assert x.origin == "Tehran"
    assert x.destinations == ("Shiraz",)
    assert x.route_order_explicit is True


def test_persian_multi_city_and_budget():
    x = analyze_traveler_intent_v2("۴ روز شیراز و اصفهان، بودجه ۵ میلیون تومان")
    assert x.destinations == ("Shiraz", "Isfahan")
    assert x.budget is not None
    assert x.budget.amount == Decimal("5000000")
    assert x.budget.unit == "TOMAN"


def test_iso_gregorian_dates():
    x = analyze_traveler_intent_v2("Plan a trip to Yazd from 2026-11-03 to 2026-11-06")
    assert x.travel_dates is not None
    assert x.travel_dates.start_date == date(2026, 11, 3)
    assert x.travel_dates.end_date == date(2026, 11, 6)
    assert x.base.duration_days is None
    assert "duration_days" not in x.unresolved_fields


def test_jalali_date_is_not_converted_silently():
    x = analyze_traveler_intent_v2("برای شیراز برنامه سفر از ۱۴۰۵/۰۸/۱۵ میخوام")
    assert x.travel_dates is None
    assert "travel_dates" in x.unresolved_fields


def test_invalid_date_is_not_used():
    x = analyze_traveler_intent_v2("Plan a 3 day trip to Shiraz on 2026-02-31")
    assert x.travel_dates is None
    assert "travel_dates" in x.unresolved_fields


def test_reverse_date_range_requires_clarification():
    x = analyze_traveler_intent_v2("Trip to Yazd from 2026-11-08 to 2026-11-03")
    assert x.travel_dates is None
    assert "travel_dates" in x.unresolved_fields


def test_budget_does_not_guess_currency():
    x = analyze_traveler_intent_v2("Plan a 3 day trip to Tehran. Budget 500")
    assert x.budget is None


def test_budget_does_not_guess_exchange_rates():
    x = analyze_traveler_intent_v2("Plan a 3 day trip to Tehran under 600 USD")
    assert x.budget is not None
    assert x.budget.amount == Decimal("600")
    assert x.budget.unit == "USD"


def test_conflicting_budgets_are_not_arbitrarily_selected():
    x = analyze_traveler_intent_v2("Plan a 3 day trip to Tehran. Budget 300 USD or 500 EUR")
    assert x.budget is None
    assert "budget" in x.unresolved_fields


def test_price_reference_is_not_budget():
    x = analyze_traveler_intent_v2("Tell me about a 20 USD museum ticket in Tehran")
    assert x.budget is None


def test_no_fake_destination_dates_or_budget():
    x = analyze_traveler_intent_v2("I enjoy food and nature")
    assert x.destinations == ()
    assert x.travel_dates is None
    assert x.budget is None


def test_v1_contract_unchanged():
    original = analyze_traveler_intent("۳ روز شیراز، معماری و غذاهای محلی دوست دارم")
    x = analyze_traveler_intent_v2("۳ روز شیراز، معماری و غذاهای محلی دوست دارم")
    assert x.base == original
