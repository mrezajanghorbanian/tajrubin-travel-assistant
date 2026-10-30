# Tajrubin Travel Assistant

An open-source, local-first AI travel assistant for destination discovery, travel questions, itinerary planning, and trip replanning.

The first knowledge pack focuses on Iran. The architecture is designed to support additional countries without retraining the core language model.

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

Early public extraction and architecture phase.

The production Tajrubin marketplace backend remains a separate private system.

## Retrieval evaluation

See [offline bilingual retrieval evaluation](docs/RETRIEVAL_EVALUATION.md) for the synthetic fixture, metric definitions, limits and reproducible commands.

See [the public Iran knowledge pack](docs/IRAN_KNOWLEDGE_PACK.md) for the source-attributed records and runnable Persian/English examples.
