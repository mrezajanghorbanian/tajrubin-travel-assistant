# Deterministic Itinerary Scheduler v1

This module schedules an **ordered set of selected activities**, only when sufficient dated opening windows and directed travel-time evidence have been supplied. It does **not** select attractions, optimize routes, use Google Maps, check live hours, or create reservations.

## Inputs and output

- `TripDraftSpecificationV1`: single city, day count, explicit start date.
- `VisitCandidateV1`: stable ID, name, city, day assignment, visit duration, knowledge document ID, date-specific opening windows with source ID.
- `TravelTimeV1`: directed from/to activity IDs, supplied minute duration and source ID.
- `ItineraryScheduleV1`: `provisional`, `blocked`, or `infeasible`; scheduled activities and source IDs for a successful draft, or typed issues for a failure.

## Validation guarantees

- No fabricated opening hours, prices or travel-time edges.
- No invented visit duration.
- No reverse-edge inference.
- No schedule outside the specified daily window or a candidate's supplied opening windows.
- No multi-city itinerary until intercity transfers and routing semantics are implemented.
- No partial result misrepresented as a feasible completed itinerary.
- `verified_live` is always false and `requires_independent_verification` always true.
- The schedule is only as trustworthy as the upstream supplied evidence; source IDs indicate traceability, not independent verification.

## Test fixture

Tests use synthetic activity and opening-hour records. **Fixture times are invented solely to validate algorithm behavior**, not to describe real Tehran museums, attractions or transit conditions.

```bash
python -m pytest tests/test_itinerary_scheduler.py -q
```

## Next development tasks

1. Attraction data ingestion with rigorous provenance, source freshness, coordinates and accessibility.
2. Verified travel-time connectors and controlled caching.
3. Source freshness thresholds by information type and explicit stale-data blocking.
4. Route ordering, multi-city transport, traveler pace and accessibility constraints.
5. Benchmark-based optimization and realistic sample itinerary evaluation before public UI display.
