"""Bounded, rule-based traveler intent extraction for the public MVP.

Deliberately conservative: unsupported locations, dates, budgets, and vague
preferences remain unspecified. This module does not call an LLM or APIs.
"""

from __future__ import annotations

import argparse
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

IntentType = Literal["trip_planning", "destination_discovery", "travel_question"]
Interest = Literal["history", "food", "art_culture", "nature", "adventure"]
Avoidance = Literal["crowds", "tourist_hotspots"]
Pace = Literal["relaxed", "balanced", "active"]

# Extensible, explicit aliases for the initial Iran destinations.
_CITY_ALIASES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Tehran", ("tehran", "تهران")),
    ("Shiraz", ("shiraz", "شیراز")),
    ("Isfahan", ("isfahan", "esfahan", "اصفهان")),
    ("Yazd", ("yazd", "یزد")),
    ("Kashan", ("kashan", "کاشان")),
    ("Tabriz", ("tabriz", "تبریز")),
    ("Kerman", ("kerman", "کرمان")),
    ("Qeshm", ("qeshm", "gheshm", "قشم")),
)

_NUMBER_WORDS = {
    "یک": 1, "دو": 2, "سه": 3, "چهار": 4, "پنج": 5,
    "شش": 6, "هفت": 7, "هشت": 8, "نه": 9, "ده": 10,
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
}

_NUMBER = r"(?:[0-9]{1,3}|" + "|".join(
    sorted(_NUMBER_WORDS, key=len, reverse=True)
) + r")"
_DAY_REGEX = re.compile(
    rf"(?<!\w)(?P<number>{_NUMBER})\s*-?\s*(?:days?|روز(?:ه)?)(?!\w)",
    re.IGNORECASE,
)
_PARTY_REGEX = re.compile(
    rf"(?<!\w)(?P<number>{_NUMBER})\s*(?:people|persons|travel(?:l)?ers|adults|نفر|آدم)(?!\w)",
    re.IGNORECASE,
)
_INTEREST_PATTERNS: tuple[tuple[Interest, tuple[str, ...]], ...] = (
    ("history", ("history", "historic", "heritage", "تاریخ", "تاریخی", "میراث")),
    ("food", ("food", "cuisine", "restaurant", "restaurants", "غذا", "غذای", "خوراک", "رستوران")),
    ("art_culture", ("art", "arts", "architecture", "museum", "museums", "culture", "هنر", "هنری", "معماری", "موزه", "فرهنگ")),
    ("nature", ("nature", "forest", "forests", "mountains", "طبیعت", "جنگل", "کوه", "کوهستان")),
    ("adventure", ("adventure", "hiking", "trekking", "climbing", "ماجراجویی", "کوهنوردی", "پیاده روی")),
)
_AVOIDANCE_PATTERNS: tuple[tuple[Avoidance, tuple[str, ...]], ...] = (
    ("crowds", (r"\bavoid crowds\b", r"\bnot crowded\b", r"خلوت", r"دور از شلوغی", r"بدون شلوغی")),
    ("tourist_hotspots", (r"\bnon touristy\b", r"\bless touristy\b", r"\bavoid tourist", r"توریستی\s+(?:رو|را)\s+(?:نمی\s*خوام|نمی\s*خواهم)", r"غیر توریستی")),
)
_PACE_PATTERNS: tuple[tuple[Pace, tuple[str, ...]], ...] = (
    ("relaxed", (r"\bslow paced\b", r"\brelaxed pace\b", r"\beasy itinerary\b", r"سفر آرام", r"برنامه سبک", r"سفر آروم")),
    ("active", (r"\bfast paced\b", r"\bpacked itinerary\b", r"برنامه فشرده", r"سفر فشرده")),
    ("balanced", (r"\bbalanced pace\b", r"برنامه متعادل")),
)

_DIGITS = str.maketrans(
    "۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩",
    "01234567890123456789",
)


class _Request(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    text: str = Field(min_length=3, max_length=2000)


class TravelerIntentV1(BaseModel):
    """Typed interpretation; null means unknown, not an assumed default."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)
    intent_version: Literal["1.0"] = "1.0"
    extraction_method: Literal["rule_based"] = "rule_based"
    request: str = Field(min_length=3, max_length=2000)
    intent_type: IntentType
    destination: str | None = None
    duration_days: int | None = Field(default=None, ge=1, le=30)
    party_size: int | None = Field(default=None, ge=1, le=30)
    interests: tuple[Interest, ...] = ()
    avoid: tuple[Avoidance, ...] = ()
    pace: Pace | None = None
    missing_required: tuple[Literal["destination", "duration_days"], ...] = ()
    clarification_question: str | None = None


def _normalize(text: str) -> str:
    text = text.translate(_DIGITS).replace("ي", "ی").replace("ك", "ک")
    text = text.replace("\u200c", " ").replace("-", " ")
    return " ".join(text.casefold().split())


def _word_matches(text: str, word: str) -> bool:
    return re.search(r"(?<!\w)" + re.escape(word) + r"(?!\w)", text) is not None


def _read_number(raw: str) -> int | None:
    if raw.isdecimal():
        return int(raw)
    return _NUMBER_WORDS.get(raw)


def _extract_count(text: str, pattern: re.Pattern[str]) -> int | None:
    counts: set[int] = set()
    for match in pattern.finditer(text):
        # "in three days" / "سه روز دیگه" indicates departure, not duration.
        if pattern is _DAY_REGEX:
            after = text[match.end():match.end() + 9]
            before = text[max(0, match.start() - 4):match.start()]
            if re.match(r"\s*(?:later|دیگه|بعد)", after) or re.search(r"\bin\s*$", before):
                continue
        value = _read_number(match.group("number"))
        if value is not None and 1 <= value <= 30:
            counts.add(value)
    return next(iter(counts)) if len(counts) == 1 else None


def _matches_any(text: str, variants: tuple[str, ...]) -> bool:
    return any(_word_matches(text, value) for value in variants)


def _matches_pattern(text: str, variants: tuple[str, ...]) -> bool:
    return any(re.search(value, text) is not None for value in variants)


def _interest_is_negated(text: str, start: int, end: int) -> bool:
    # Only suppress *explicit local* negation. Broader linguistic polarity is
    # deferred to a future LLM-backed extractor; do not claim full NLP support.
    before = text[max(0, start - 24):start]
    after = text[end:end + 22]
    return (
        re.search(r"(?:\bavoid\s+|\bno\s+|\bnot into\s+|بدون\s+)$", before) is not None
        or re.search(r"^\s*(?:رو|را)?\s*(?:دوست ندارم|نمی\s*خوام|نمی\s*خواهم)", after) is not None
    )


def _extract_interests(text: str) -> tuple[Interest, ...]:
    result: list[Interest] = []
    for interest, terms in _INTEREST_PATTERNS:
        for term in terms:
            match = re.search(r"(?<!\w)" + re.escape(term) + r"(?!\w)", text)
            if match and not _interest_is_negated(text, match.start(), match.end()):
                result.append(interest)
                break
    return tuple(result)


def _detect_destination(text: str) -> str | None:
    choices = [
        city for city, aliases in _CITY_ALIASES
        if _matches_any(text, aliases)
    ]
    return choices[0] if len(choices) == 1 else None


def _type_of_request(text: str, duration_days: int | None) -> IntentType:
    if duration_days is not None or _matches_pattern(
        text,
        (r"\bitinerary\b", r"\bplan (?:a |my |our )?trip\b", r"\btrip plan\b", r"برنامه سفر", r"برنامه ریزی سفر", r"سفر\s+\S+\s+روز"),
    ):
        return "trip_planning"
    if _matches_pattern(
        text,
        (r"\brecommend\b", r"\bdiscover\b", r"\bwhere (?:should|to) (?:i |we )?go\b", r"کجا برم", r"پیشنهاد", r"کشف", r"جاهای دیدنی"),
    ):
        return "destination_discovery"
    return "travel_question"


def analyze_traveler_intent(text: str) -> TravelerIntentV1:
    """Extract only explicit, supported facts; no inferred dates or budgets."""
    original = _Request(text=text).text
    normalized = _normalize(original)

    destination = _detect_destination(normalized)
    days = _extract_count(normalized, _DAY_REGEX)
    party = _extract_count(normalized, _PARTY_REGEX)
    kind = _type_of_request(normalized, days)

    interests = _extract_interests(normalized)
    avoid = tuple(
        label for label, patterns in _AVOIDANCE_PATTERNS
        if _matches_pattern(normalized, patterns)
    )
    matched_paces = [
        label for label, patterns in _PACE_PATTERNS
        if _matches_pattern(normalized, patterns)
    ]
    pace = matched_paces[0] if len(matched_paces) == 1 else None

    missing: list[Literal["destination", "duration_days"]] = []
    if kind == "trip_planning":
        if destination is None:
            missing.append("destination")
        if days is None:
            missing.append("duration_days")

    persian = re.search(r"[\u0600-\u06ff]", original) is not None
    question: str | None = None
    if missing:
        if missing[0] == "destination":
            question = "برای کدام مقصد برنامه سفر می‌خواهید؟" if persian else "Which destination should I plan for?"
        else:
            question = "سفرتان چند روز است؟" if persian else "How many days will you travel?"

    return TravelerIntentV1(
        request=original,
        intent_type=kind,
        destination=destination,
        duration_days=days,
        party_size=party,
        interests=interests,
        avoid=avoid,
        pace=pace,
        missing_required=tuple(missing),
        clarification_question=question,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Conservative travel request analyzer")
    parser.add_argument("request", help="English or Persian natural-language request")
    args = parser.parse_args()
    print(analyze_traveler_intent(args.request).model_dump_json(indent=2))


if __name__ == "__main__":
    main()


__all__ = ["TravelerIntentV1", "analyze_traveler_intent"]
