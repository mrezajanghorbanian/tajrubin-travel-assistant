# Traveler Intent Contract v1

This is a conservative, deterministic bilingual (English/Persian) extraction module for **explicitly stated** traveler preferences. It is **not** a complete natural-language understanding system, a geocoder, a booking engine or an LLM.

## Use

```bash
python -m app.assistant.traveler_intent "۳ روز شیراز، معماری و غذاهای محلی دوست دارم"
python -m app.assistant.traveler_intent "Plan a trip to Tehran for 2 people"
python -m pytest tests/test_traveler_intent.py -q
```

Returns JSON with: intent version, request type, supported named destination, duration (1–30 days), party size (1–30), named interests, avoidance preferences, pace, missing fields and at most one focused clarification question.

## Principles and limitations

- Missing or ambiguous properties remain `null`. Do **not** fabricate a date, budget, location, party size or preference.
- Destination alias list is deliberately small and currently Iran-focused; it must expand through versioned configuration with geographic disambiguation, not ad hoc model guesses.
- Multi-city travel cannot yet be accurately modeled. When several recognized cities are present, the single-destination field remains null, prompting clarification.
- Pattern matching and negation are limited: use benchmark-driven intent extraction and human review before relying on complex requests.
- The module never connects to the web, spends money, collects location or makes bookings.
- The supported request types are `trip_planning`, `destination_discovery`, and `travel_question`; these types are preliminary routing hints.
- Avoid retaining raw user inputs in telemetry without purpose, consent and redaction controls.

## Next iteration

Version the entity ontology, support multiple stops and dates, derive language and script carefully, add typed budget/currency handling, provenance of extracted constraints and a gold evaluation corpus.
