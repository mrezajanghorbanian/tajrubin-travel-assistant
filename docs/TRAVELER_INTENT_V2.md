# Traveler Intent v2 — Contract and Scope

v2 is a conservative additive extension of the stable `TravelerIntentV1` contract.

## Commands

```bash
python -m app.assistant.traveler_intent_v2 "۴ روز شیراز و اصفهان، بودجه ۵ میلیون تومان"
python -m app.assistant.traveler_intent_v2 "Plan a trip to Yazd from 2026-11-03 to 2026-11-06"
python -m pytest tests/test_traveler_intent_v2.py -q
```

## Schema

- `base`: original v1 intent, backward compatible.
- `origin`: explicit departure city **only** when matched by a known from/to expression.
- `destinations`: unique recognized destinations, in textual mention order.
- `route_order_explicit`: whether text contains an ordering signal. This is not a verified routing plan.
- `travel_dates`: explicit valid **Gregorian ISO 8601** dates only; no implicit calendar conversion.
- `budget`: positive amount, currency unit, and raw matched expression, with **no** exchange-rate conversion.
- `unresolved_fields`: unknown or conflicting details requiring clarification.
- `clarification_question`: a single, focused missing-information question or null.

## Safety and correctness constraints

1. Do not infer calendar systems from a number that looks like a date. A Jalali-style date is unresolved until calendar support is explicitly implemented.
2. A string like `Tehran and Shiraz` expresses destinations, not a travel route order; destination mention order is distinct from itinerary order.
3. Return budget only with explicit currency and relevant budget language. Museum ticket prices are not traveler budgets.
4. Distinguish departure origin from travel stops whenever an unambiguous `from X to Y` pattern exists.
5. The alias list only contains initial Iran destinations and must be replaced by an authoritative destination registry later.
6. Values returned by this module must not authorize bookings, payments, travel restrictions, or location tracking.
7. No personally identifying traveler data should be persisted by default.

## Known limits

- English and Persian fixed-rule coverage is intentionally narrow; blended wording, flexible dates, implicit budgets and complex multi-stop sequencing require evaluation and further work.
- v1 and v2 are *extraction contracts*, not a trained destination planner or a validated source of travel facts.
- v2 reports recognized place mentions even when route order is unclear; a planning engine must seek clarification before scheduling those stops.
- User-defined currency unit `TOMAN` is preserved, not automatically transformed to rial.
- ISO departure and return date ranges are represented as dates; exact trip-night/day calculations require explicit convention and should not be silently inferred.

## Evaluation requirements

Build a gold dataset with Persian digits, Arabic digit forms, Jalali/Gregorian ambiguities, mixed language, optional origin, reversed ranges, multiple currency figures, place-name collisions, negation and prompt-injection strings. Prioritize false-positive rate over raw extraction coverage.
