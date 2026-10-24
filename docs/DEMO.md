# Offline Travel QA Demo

This is a working, **non-generative** first slice of the Tajrubin Travel AI project, not the promised production travel companion.

## Requirements

- Python 3.11+
- No account, paid LLM, external API or API key required

## Start from a clean clone

```bash
python -m venv .venv
# Activate the environment for your operating system
python -m pip install -e '.[dev]'
python -m pytest -q
```

## Run a question

```bash
python -m app.assistant.demo 'Tehran museums and culture' --country IR --city Tehran
python -m app.assistant.demo 'Tehran museums' --format json
python -m app.assistant.demo 'astronaut orbital station' --format json
```

The first commands return snippets from `knowledge/iran/destinations/tehran.md`, with document ID and review date. The last returns **insufficient_evidence**.

You may load other source documents:

```bash
python -m app.assistant.demo 'Your travel question' --knowledge-root ./knowledge
```

Knowledge documents must comply with the schema in `app/knowledge/contract.py`. Duplicate IDs, missing paths and unsafe symlinked files are rejected.

## Limitations

- No itinerary planner, live map API, booking, autonomous web research or LLM answer generation yet.
- Lexical retrieval is not semantically robust; irrelevant or partial matches are possible.
- Knowledge snippets are **provisional**, not externally verified answers.
- Current Tehran sample has no external source URLs. Never represent it as a verified tourism authority.
- Do not treat old content as reliable for current opening hours, transport changes, pricing or safety conditions.
- This CLI is intended for developers and testers; the traveler-facing web app is a future milestone.

## Intended public beta

A mobile-friendly interface for asking naturally, receiving trusted travel information, editing feasible multi-day plans and visualizing routes. This demo is the first reproducible vertical slice on the path to that goal.
