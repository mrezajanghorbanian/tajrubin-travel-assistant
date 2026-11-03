# Tajrubin Travel Assistant

An open-source, local-first AI travel assistant for destination discovery, travel questions, itinerary planning, and trip replanning.

The first knowledge pack focuses on Iran. The architecture is designed to support additional countries without retraining the core language model.

The product target is a **Persian-first conversational travel agent**: the
existing local model works with session context and travel tools to help users
plan and revise trips in chat. Domestic Iran travel comes first; foreign
destinations follow. See [the product direction and active sprint gates](docs/CONVERSATIONAL_AGENT.md).
This connected agent journey is still under development; the current offline
command provides deterministic QA and planning readiness.

The [CORE-01 local-model intake entry point](docs/LOCAL_MODEL_TURN.md) runs
one real Persian model turn with the existing local provider:
`python -X utf8 -m app.assistant.local_model_turn 'سه روز شیراز'`.
It does not yet maintain a conversation, retrieve places or generate a trip.

## Initial Goals

The [unified offline assistant](docs/LOCAL_ASSISTANT.md) is runnable with
`python -X utf8 -m app.assistant 'کاخ گلستان'`. It handles local knowledge
questions and reports missing or resolved initial trip-planning details.

- Answer grounded travel questions
- Recommend destinations and experiences
- Build multi-day itineraries
- Replan parts of an existing trip
- Use local LLMs through provider-neutral interfaces
- Retrieve destination knowledge through RAG
- Show sources for knowledge-grounded answers
- Keep travel knowledge separate from model weights
- Support additional countries through independent knowledge packs

## Architecture Direction

User
  -> Travel Assistant
      -> Intent Understanding
      -> Retrieval
          -> Travel Knowledge Base
      -> Recommendation
      -> Trip Planning
      -> Replanning
      -> Local LLM Provider

## Knowledge

Travel information is stored as maintainable source documents and metadata.

The vector index is derived data and can be rebuilt from the source knowledge base.

Initial structure:

knowledge/
  iran/
    destinations/
    attractions/
    experiences/
    food/
    culture/
    transport/
    practical/

## Local Model Support

The project will remain model-provider agnostic.

Planned adapters include:

- Ollama
- LM Studio
- OpenAI-compatible local endpoints

## Project Status

Runnable public prototype with local source-attributed QA, Persian/English
retrieval and initial planning readiness. Scheduling and signed-catalog
components remain separate, bounded libraries.

See [current status and CI evidence](docs/STATUS.md) for implemented slices,
remaining product gaps and the review map. The goals above include future
work; the offline command does not generate a verified traveler itinerary.

The production Tajrubin marketplace backend remains a separate private system.

Planned feature [F-BOOK-01: flight, hotel and experience integrations](docs/BOOKING_INTEGRATION.md)
adds a staged path from live comparison and provider checkout links to
customer-approved booking. These connections are not implemented or enabled.

## Retrieval evaluation

See [offline bilingual retrieval evaluation](docs/RETRIEVAL_EVALUATION.md) for synthetic suites, the repository-corpus gate, metric definitions, limits and reproducible commands.

See [the public Iran knowledge pack](docs/IRAN_KNOWLEDGE_PACK.md) for the source-attributed records and runnable Persian/English examples.

The [CORE-02 conversation checkpoint](docs/LOCAL_MODEL_SESSION.md) supports
multiple Persian intake turns in one in-memory process:
`python -X utf8 -m app.assistant.local_model_session`. It retains literal user
messages and pending questions within explicit capacity limits. Optional grounded
search and literal trip-state slots are described below; a complete editable
itinerary remains open.

The same session supports [model-selected grounded search](docs/GROUNDED_SESSION.md)
with `--grounded`: read-only public Iran knowledge, literal user-anchored city/query
arguments, original source IDs/URLs/review dates and explicit no-evidence results.
This does not create recommendations, verified live facts or an itinerary.

Use `--trip-state` in that same session for [literal trip-state slots](docs/TRIP_STATE_SESSION.md)
with source-message numbers and atomic partial corrections. This includes
grounded search; the stored statements still need semantic confirmation and
normalization before they can become planner inputs.

In trip-state mode an [explicit follow-up policy](docs/TRIP_STATE_SESSION.md#required-details-follow-up-policy)
asks for missing required details when the model gives no question, preserving
question provenance. Complete literal slots still require validation before planning.
