"""Conservative bilingual traveler-intent extraction contracts."""

import json
import subprocess
import sys

import pytest
from pydantic import ValidationError

from app.assistant.traveler_intent import analyze_traveler_intent


def test_persian_trip_with_digits_and_interests():
    x = analyze_traveler_intent("۳ روز شیراز، معماری و غذاهای محلی دوست دارم")
    assert x.intent_type == "trip_planning"
    assert x.destination == "Shiraz"
    assert x.duration_days == 3
    assert x.interests == ("food", "art_culture")
    assert x.missing_required == ()
    assert x.clarification_question is None


def test_persian_spelled_number_and_avoidance():
    x = analyze_traveler_intent("سه روز شیراز، جاهای خیلی توریستی رو نمی خوام، هنر و غذا دوست دارم")
    assert x.duration_days == 3
    assert "tourist_hotspots" in x.avoid
    assert "art_culture" in x.interests
    assert "food" in x.interests


def test_english_explicit_party_and_trip():
    x = analyze_traveler_intent("Plan a four days trip to Tehran for 2 people with art and nature")
    assert x.intent_type == "trip_planning"
    assert x.destination == "Tehran"
    assert x.duration_days == 4
    assert x.party_size == 2
    assert x.interests == ("art_culture", "nature")


def test_unicode_and_arabic_digits():
    x = analyze_traveler_intent("٤ روز اصفهان برای ۲ نفر")
    assert x.destination == "Isfahan"
    assert x.duration_days == 4
    assert x.party_size == 2


def test_no_invented_trip_details():
    x = analyze_traveler_intent("جاهای دیدنی یزد را پیشنهاد بده")
    assert x.intent_type == "destination_discovery"
    assert x.destination == "Yazd"
    assert x.duration_days is None
    assert x.party_size is None
    assert x.pace is None


def test_missing_destination_one_focused_question_in_persian():
    x = analyze_traveler_intent("برای ۵ روز برنامه سفر میخوام")
    assert x.missing_required == ("destination",)
    assert x.clarification_question == "برای کدام مقصد برنامه سفر می‌خواهید؟"


def test_missing_duration_one_focused_question_in_english():
    x = analyze_traveler_intent("Plan a trip to Shiraz")
    assert x.missing_required == ("duration_days",)
    assert x.clarification_question == "How many days will you travel?"


def test_ambiguous_multiple_destinations_are_not_guessed():
    x = analyze_traveler_intent("Plan a 5 day trip to Tehran and Shiraz")
    assert x.destination is None
    assert x.missing_required == ("destination",)


def test_conflicting_duration_does_not_pick_arbitrary_number():
    x = analyze_traveler_intent("Plan a 3 day or 5 day trip to Tehran")
    assert x.duration_days is None


def test_exceeds_supported_duration_not_asserted():
    x = analyze_traveler_intent("Plan a 90 day trip to Tehran")
    assert x.duration_days is None


def test_negated_interest_is_not_positive():
    x = analyze_traveler_intent("I want Tehran, no museums, but I like food")
    assert "art_culture" not in x.interests
    assert "food" in x.interests


def test_pace_and_avoid_crowds():
    x = analyze_traveler_intent("I want a relaxed pace in Tehran, avoid crowds")
    assert x.pace == "relaxed"
    assert "crowds" in x.avoid


def test_departure_time_is_not_duration():
    x = analyze_traveler_intent("Plan a trip to Tehran in 3 days")
    assert x.duration_days is None


def test_question_only_not_forced_into_planning():
    x = analyze_traveler_intent("Tell me about Tehran museums")
    assert x.intent_type == "travel_question"
    assert x.missing_required == ()


@pytest.mark.parametrize("text", ["", "x", "a" * 2001])
def test_invalid_text_rejected(text):
    with pytest.raises(ValidationError):
        analyze_traveler_intent(text)


def test_cli_emits_structured_json():
    result = subprocess.run(
        [sys.executable, "-m", "app.assistant.traveler_intent", "۳ روز شیراز"],
        check=True, capture_output=True, text=True,
    )
    payload = json.loads(result.stdout)
    assert payload["destination"] == "Shiraz"
    assert payload["duration_days"] == 3
