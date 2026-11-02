# F-BOOK-01: Flight, hotel and experience integrations

Status: **planned; not implemented or enabled**. Added to the delivery plan
on 2026-11-02 at the owner's request. This document authorizes planning, not
paid API activation, account creation, production deployment or purchases.

## Customer outcome

A traveler describes dates, origin/destinations, party, budget and preferences
in Persian or English. Tajrubin obtains available flight, accommodation and
experience offers from connected suppliers, explains suitable combinations,
and prepares a coherent trip. Initially the traveler completes checkout with
the provider. A later stage may complete an explicitly approved reservation
through a supported booking integration.

"Best" means the strongest fit to that traveler's stated criteria among
offers actually checked. It does not mean complete website coverage or a
guaranteed globally cheapest trip. Provider failures and missing coverage
must be visible rather than interpreted as proof that no offers exist.

## Scope and rollout sequence

| Work package | Deliverable | Dependency and exit gate |
| --- | --- | --- |
| BOOK-01 / access and coverage | Capability matrix for candidate flight, hotel and experience providers, including target-market/Iran coverage, sandbox, search, redirect, booking, cancellation, limits and costs | Maintainer verifies current documentation and access eligibility; unknown capabilities stay unverified; choose providers only after assessment |
| BOOK-02 / contracts and offline adapters | Provider-neutral search requests and offer/error contracts; deterministic synthetic adapters for all three verticals | Existing intent/readiness boundaries; contract tests reject missing prices, invalid currency/date/party context and ambiguous offer identity; no live credentials required |
| BOOK-03 / live search and redirect pilot | One verified connector per vertical, bounded requests, current availability/price checks and provider checkout links | BOOK-01/02, approved access and any costs, safe URL handling; demonstrate real follow-up search/recheck in sandbox and authorized pilot; incomplete verticals remain visibly unavailable |
| BOOK-04 / combined trip comparison | Rank feasible flight + stay + experience combinations with explanations and alternative choices | Dated offer evidence plus M2 constraint checks; M3 Persian/English comparison flow; hard constraints cannot be traded away for a lower price |
| BOOK-05 / approved booking | Reprice/recheck, show exact terms, collect explicit approval, create supported orders and verify final provider state | Separate provider booking permission/commercial arrangements; M4 checks; payment and personal-data handling established; idempotency and uncertain-result recovery tested |
| BOOK-06 / post-booking support | Show confirmed references/vouchers and supported change/cancellation options with their fees and status | BOOK-05 plus provider capabilities; test reconciliation and partial failures; no unsupported refund promise or silent fee-bearing action |

BOOK-02 can run alongside M1/M2 with fixtures. Live user rollout is the
conditional M6 workstream and depends on the relevant M3/M4 acceptance gates.
BOOK-03 delivers discovery and checkout handoff before BOOK-05 adds direct
booking. No calendar estimate is committed before access, coverage and costs
are known. Implementation ownership and delivery dates are assigned when
each work package is scheduled.

## Provider integration boundary

Use official APIs or approved partner integrations for structured inventory
and transactions. Each adapter declares its supported capabilities rather
than pretending all providers expose the same operations.

Browser-based integration is a separately assessed fallback for a named site
and permitted workflow. It requires versioned flow tests, bounded actions and
user handoff for unsupported authentication or verification. It must not imply
that the agent knows every booking site, bypass access controls, or replace a
reliable order-status integration with a guessed confirmation from page text.

Candidate references, not selected or activated providers:

- [Amadeus flight API FAQ](https://admin.developers.amadeus.com/self-service/apis-docs/guides/developer-guides/faq/): assess flight search, repricing, orders and ticket-issuance arrangements.
- [Booking.com accommodations API](https://developers.booking.com/demand/docs/accommodations/about-accommodation): assess search, availability, redirect and permitted order integration.
- [Viator Partner API](https://docs.viator.com/partner-api/technical/): assess experience inventory, availability and transactional endpoints for the actual access level.

Recheck these official references during BOOK-01; this plan does not assert
approved access, universal inventory, current prices or Iran coverage for any
candidate. Domestic suppliers may be assessed through the same matrix.

## Offer evidence and comparison rules

The future contracts must retain:

- Provider and stable offer/product identifiers, originating request context,
  traveler/guest mix, dates/time zones, retrieval time and validity/recheck
  policy. Cached descriptions are distinct from current availability.
- Original currency, total payable amount, mandatory taxes/fees, inclusions,
  optional extras and cancellation/change terms. Unknown mandatory costs must
  not be shown as zero or ranked as a verified cheaper total.
- Flight segments, baggage and connection constraints; hotel location, room
  and occupancy terms; experience date, start time, duration, meeting point
  and participation restrictions, where supplied by the provider.
- Source/checkout reference and an explicit distinction between synthetic,
  cached, freshly checked, unavailable, expired and confirmed information.

Ranking first applies hard date, party, budget and feasibility constraints,
then explains preference tradeoffs such as price, travel time, cancellation,
hotel location and experience fit. Do not infer currencies or exchange rates;
any conversion needs a dated source and visible conversion assumptions.
Unknown travel times, opening windows or accessibility claims remain unknown.
Customer confirmation is required when missing facts prevent a reliable plan.

Flight arrival, accommodation check-in/out, experience times, time zones and
transfer buffers must be compatible using supplied evidence. A recommendation
is not an inventory hold or a confirmed booking.

## Transaction and data boundaries

Immediately before booking, recheck the chosen offer and show the actual
price, currency, terms and supplier. A material change invalidates prior
approval. Keep payment with a suitable provider-hosted/tokenized flow; never
place card details, passports, login credentials or real traveler fixtures in
the public repository or diagnostic logs. Collect and transmit only required
traveler data with consent. Credentials remain outside source control.

Persist request/order correlation and idempotency where supported. A timeout
after submission is an uncertain result, not permission to purchase again;
query provider state or reconcile before retrying. Report "booked" only after
provider confirmation with the corresponding reference and status.

A combined trip spans separate suppliers and is not an atomic transaction.
If only some components book, display exactly what succeeded, what failed,
and available recovery options. Do not silently cancel confirmed components,
accept new fees or promise automatic full rollback/refund.

## Acceptance and evaluation

Required before the corresponding stage is declared complete:

1. Adapter tests cover flight, hotel and experience request/response contracts,
   unsupported capability, malformed provider data and deterministic errors.
2. Comparison cases cover mandatory fees, occupancy/baggage differences,
   currency mismatch, unavailable inventory and stale/expired offers.
3. Trip cases reject conflicting times, missing transfer evidence and violated
   hard constraints; unknown facts cannot become fabricated schedule inputs.
4. Ranking is reproducible with explicit criteria. Persian/English flows show
   alternatives, sources, freshness and reasons; no worldwide-best claim.
5. Live connectors have recorded sandbox/pilot evidence distinct from fixture
   success, including a real availability/price recheck. Secrets and personal
   data are excluded from public proof artifacts.
6. Booking tests enforce approval for the exact offer and terms, detect price
   changes, prevent duplicate purchase and reconcile uncertain submissions.
7. Partial multi-provider success and supported cancellation/change failures
   preserve truthful order state and require approval for fee-bearing actions.
8. Timeouts, rate limits and provider outages have bounded handling; estimates
   and static knowledge are never substituted for live inventory or orders.

Use offline fixtures for normal CI and separately authorized integration tests
for external systems. No CI test may spend money or create a real reservation.
Record coverage, request cost and latency before setting numerical production
targets. Existing local QA remains usable independently of booking connectors.

See [delivery milestones](PROJECT_PLAN.md), [current prototype evidence](STATUS.md)
and [trip-preview boundaries](TRIP_PREVIEW.md). The private Tajrubin backend
remains separate. No provider contract, production connection or booking
capability is delivered by this documentation change.
