# Traveler Trip Preview — First Integrated Product Slice

`app/assistant/trip_preview.py` is a conservative traveler-facing orchestration boundary. It combines natural-language traveler intent, planning readiness, approved signed catalog data and deterministic day scheduling.

## CLI

```bash
python -m app.assistant.trip_preview "Plan a 1 day trip to Tehran on 2026-11-03"
```

Without signed approved attraction data and explicit visit selections, the tool **does not invent activities**. It returns a machine-readable status explaining what is missing.

## Supported flow

Traveler request → typed intent → clarification when necessary → explicit date and attraction selections → signed release verified against current editorial approval → freshness-checked dated activity data → supplied directional travel evidence → provisional daily itinerary.

Returns `TripPreviewV1` with status, parsed readiness, optional schedule, provenance document IDs and `live_verified=False`.

## Restrictions

- **No live attraction inventory is currently connected.** Synthetic fixtures are used exclusively in tests.
- Supports a single destination city, maximum 30 days; multi-city itineraries, transport estimates and autonomous attraction discovery are still unimplemented.
- The caller must supply attraction selections and directed travel-time estimates. Missing data causes a blocked or explanatory response, not fictitious hours or routes.
- A signed release proves integrity of endorsed data, not factual accuracy. Editorially approved data still requires independent verification.
- The editorial review database is consulted online; revocation cannot be established during an outage.
- Consumer sequence state can advance on a later rejection. This is not a cross-database transaction.
- No bookings, payments, real-time opening hours, accessibility certification or guaranteed travel plans.

## Validation

```bash
python -m pytest tests/test_trip_preview.py -q
python -m pytest -q
```

Next: real source-vetted Iranian attraction knowledge, source-aware candidate selection, trusted route-time provider, traveler-focused UI and product-level evaluations.
