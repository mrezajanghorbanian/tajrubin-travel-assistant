# Attraction Catalog v1 — Data and Provenance

This phase creates a **schema and a scheduler adapter**, not a production database with verified Iranian attractions.

## Record requirements

- Stable attraction and knowledge-document IDs; name, country, city.
- Coordinates with source identifier and geographic bounds.
- Suggested visit duration (15–480 minutes) with evidence source.
- Accessibility state (`yes`, `no`, or `unknown`), with cited source for non-unknown claims.
- Source metadata: title, kind (`official`, `editorial`, `fixture`), HTTPS URL for non-fixtures, observation date and validity cutoff.
- Date-specific opening windows linked to a source.

## Gate to Scheduler

`build_visit_candidates(catalog, selections)` refuses to convert records if:

1. An attraction is missing or IDs conflict.
2. A required location, duration, opening-hours or accessibility claim lacks source provenance.
3. The claim is stale or not yet observed on the chosen day.
4. A source is marked `fixture` (unless the caller explicitly enables `allow_synthetic_fixtures=True` for a test).
5. No dated opening window exists.

This does **not** verify a source's factual accuracy, copyright, authenticity or whether its URL can be visited now. Source freshness is **declared metadata**, not a live check.

The underlying itinerary scheduler still requires a supplied **directed travel-time estimate** between ordered activities; it never estimates routes by geographic distance. All successful schedules remain `provisional` and `verified_live=False`.

## Unit tests

```bash
python -m pytest tests/test_attraction_catalog.py tests/test_itinerary_scheduler.py -q
```

Test attraction names, times, coordinates and source URLs are synthetic and only validate code behavior. **Do not import them into the public travel knowledge catalog.**

## Next phases

1. Implement an actual bounded catalog repository and versioned ingestion tools.
2. Validate source claims against independently verified tourism sources.
3. Add confidence and evidence freshness policies by claim type (opening hours vs geography).
4. Add source-driven travel-time provider, caching and user-visible uncertainty.
5. Extend planning to accessibility, holidays and multi-city travel after evaluation.
