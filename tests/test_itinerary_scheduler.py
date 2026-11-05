"""Safety and feasibility tests for source-supplied schedules."""
from datetime import date, time
from app.assistant.planning_readiness import analyze_planning_request
from app.assistant.itinerary_scheduler import (
    OpeningWindowV1, VisitCandidateV1, TravelTimeV1, build_provisional_itinerary,
)


def spec():
    return analyze_planning_request(
        "Plan a 1 day trip to Tehran on 2026-11-03"
    ).draft_specification


def candidate(name="a", day=1, start=time(9), end=time(17), duration=60, city="Tehran"):
    return VisitCandidateV1(
        activity_id=name, title=name, city=city, day_index=day,
        duration_minutes=duration, knowledge_document_id="sample."+name,
        opening_windows=(OpeningWindowV1(
            on_date=date(2026,11,3), opens_at=start, closes_at=end,
            source_id="fixture-hours"
        ),),
    )


def test_single_activity_is_provisional_with_sources():
    result=build_provisional_itinerary(spec(), (candidate(),), ())
    assert result.status=="provisional"
    assert len(result.days)==1
    assert result.days[0].visits[0].begins_at==time(9)
    assert result.days[0].visits[0].opening_source_id=="fixture-hours"
    assert result.verified_live is False


def test_adjacent_activities_require_directed_leg():
    result=build_provisional_itinerary(spec(), (candidate(),candidate("b")),())
    assert result.status=="blocked"
    assert result.issues[0].code=="missing_travel_time"
    assert result.days==()


def test_supplied_travel_edge_influences_start():
    edge=TravelTimeV1(from_activity_id="a",to_activity_id="b",duration_minutes=35,source_id="fixture-route")
    result=build_provisional_itinerary(spec(), (candidate(),candidate("b")), (edge,))
    assert result.status=="provisional"
    second=result.days[0].visits[1]
    assert second.begins_at==time(10,35)
    assert second.travel_source_id=="fixture-route"


def test_reverse_edge_does_not_authorize_forward_trip():
    edge=TravelTimeV1(from_activity_id="b",to_activity_id="a",duration_minutes=35,source_id="fixture-route")
    result=build_provisional_itinerary(spec(), (candidate(),candidate("b")), (edge,))
    assert result.status=="blocked"
    assert result.issues[0].code=="missing_travel_time"


def test_missing_opening_window_blocks():
    x=candidate().model_copy(update={"opening_windows":()})
    result=build_provisional_itinerary(spec(),(x,),())
    assert result.status=="blocked"
    assert result.issues[0].code=="missing_opening_hours"


def test_too_long_to_fit_is_infeasible():
    result=build_provisional_itinerary(spec(),(candidate(duration=120,start=time(9),end=time(10)),),())
    assert result.status=="infeasible"
    assert result.days==()


def test_wrong_city_blocks():
    result=build_provisional_itinerary(spec(),(candidate(city="Shiraz"),),())
    assert result.status=="blocked"
    assert result.issues[0].code=="city_mismatch"


def test_missing_trip_date_blocks():
    undated=analyze_planning_request("Plan a 1 day trip to Tehran").draft_specification
    result=build_provisional_itinerary(undated,(candidate(),),())
    assert result.status=="blocked"
    assert result.issues[0].code=="missing_start_date"


def test_duplicate_activity_blocks():
    result=build_provisional_itinerary(spec(),(candidate(),candidate()),())
    assert result.status=="blocked"
    assert result.issues[0].code=="duplicate_activity"


def test_missing_day_activity_blocks_multiday():
    multiday=analyze_planning_request("Plan a 2 day trip to Tehran on 2026-11-03").draft_specification
    result=build_provisional_itinerary(multiday,(candidate(),),())
    assert result.status=="blocked"
    assert result.issues[0].code=="missing_candidates"


def test_no_fabricated_live_verification():
    result=build_provisional_itinerary(spec(),(candidate(),),())
    assert result.requires_independent_verification is True
    assert "not verified live" in result.notice


def test_atomic_failure_no_partial_itinerary():
    edge=TravelTimeV1(from_activity_id="a",to_activity_id="b",duration_minutes=35,source_id="fixture-route")
    result=build_provisional_itinerary(spec(),(candidate(),candidate("b",start=time(9),end=time(10))), (edge,))
    assert result.status=="infeasible"
    assert result.days==()
