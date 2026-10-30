"""Evidence/feasibility probes for deterministic scheduling.

Synthetic times only: never interpreted as real venue hours or routes.
"""
from datetime import date,time
from app.assistant.planning_readiness import analyze_planning_request
from app.assistant.itinerary_scheduler import (
    OpeningWindowV1,VisitCandidateV1,TravelTimeV1,build_provisional_itinerary,
)

DAY=date(2026,11,3)
SPEC=analyze_planning_request("Plan a 1 day trip to Tehran on 2026-11-03").draft_specification


def candidate(name,opening=time(9),closing=time(17),duration=60):
    return VisitCandidateV1(
        activity_id=name,title=name,city="Tehran",day_index=1,
        duration_minutes=duration,knowledge_document_id="synthetic."+name,
        opening_windows=(OpeningWindowV1(
            on_date=DAY,opens_at=opening,closes_at=closing,
            source_id="fixture.hours"),),
    )


def outcome(kind):
    a=candidate("a")
    b=candidate("b")
    if kind=="feasible_single":
        return build_provisional_itinerary(SPEC,(a,),())
    if kind=="missing_route":
        return build_provisional_itinerary(SPEC,(a,b),())
    if kind=="valid_route":
        leg=TravelTimeV1(from_activity_id="a",to_activity_id="b",duration_minutes=20,source_id="fixture.travel")
        return build_provisional_itinerary(SPEC,(a,b),(leg,))
    if kind=="reverse_only":
        leg=TravelTimeV1(from_activity_id="b",to_activity_id="a",duration_minutes=20,source_id="fixture.travel")
        return build_provisional_itinerary(SPEC,(a,b),(leg,))
    if kind=="outside_hours":
        return build_provisional_itinerary(SPEC,(candidate("a",closing=time(10),duration=120),),())
    if kind=="outside_day":
        return build_provisional_itinerary(
            SPEC,(candidate("a",opening=time(17,30),closing=time(19)),),(),
        )
    if kind=="no_hours":
        return build_provisional_itinerary(
            SPEC,(a.model_copy(update={"opening_windows":()}),),(),
        )
    if kind=="wrong_city":
        return build_provisional_itinerary(
            SPEC,(a.model_copy(update={"city":"Shiraz"}),),(),
        )
    raise ValueError("Unknown probe scenario")


EXPECTATIONS={
    "feasible_single":"provisional",
    "missing_route":"blocked",
    "valid_route":"provisional",
    "reverse_only":"blocked",
    "outside_hours":"infeasible",
    "outside_day":"infeasible",
    "no_hours":"blocked",
    "wrong_city":"blocked",
}


def test_scheduler_feasibility_probe():
    for scenario,status in EXPECTATIONS.items():
        output=outcome(scenario)
        assert output.status==status,(scenario,output.model_dump())
        assert output.verified_live is False
        assert output.requires_independent_verification is True
        if status!="provisional":
            assert output.days==()
            assert output.issues
        else:
            assert output.days[0].visits[0].knowledge_document_id.startswith("synthetic.")
