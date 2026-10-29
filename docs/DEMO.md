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

## Opt-in Persian/English retrieval

Enable the reviewed travel-term and city equivalents explicitly:

```bash
python -X utf8 -m app.assistant.demo 'موزه در تهران' --country IR --city تهران --bilingual-aliases --format json
python -X utf8 -m app.assistant.demo 'ساعت بازدید موزه' --country IR --city تهران --bilingual-aliases --format json
```

With the checked-in sample knowledge pack, the first command returns a
`provisional` answer attributed to `ir.tehran.destination`; the second returns
`insufficient_evidence` with no evidence because opening hours are unsupported.
The sample has no external source URLs and is not verified tourism authority.

`--bilingual-aliases` defaults to off. When enabled, reviewed Persian/English
equivalents apply to content terms and city filters in both directions.
Country filtering and the result limit still apply. Unknown qualifiers and
misspelled city names are not silently discarded. The existing strict request
validation also applies with this flag.

This enables bilingual **retrieval**, not answer translation: returned summaries
remain in their source document's language. It does not enable an LLM, network
lookup, paid API or live verification. Both JSON and text output preserve
source identity and the verification notice. `-X utf8` selects UTF-8 output,
including on Windows when a terminal would otherwise use a legacy encoding.

See [retrieval evaluation](RETRIEVAL_EVALUATION.md) for the fixed synthetic
benchmark, precision/recall definitions and limits. Run the end-to-end CLI
regressions with `python -m pytest tests/test_bilingual_qa_demo.py -q`.

## Limitations

- No itinerary planner, live map API, booking, autonomous web research or LLM answer generation yet.
- Lexical retrieval is not semantically robust; irrelevant or partial matches are possible.
- Knowledge snippets are **provisional**, not externally verified answers.
- Current Tehran sample has no external source URLs. Never represent it as a verified tourism authority.
- Do not treat old content as reliable for current opening hours, transport changes, pricing or safety conditions.
- This CLI is intended for developers and testers; the traveler-facing web app is a future milestone.

## Intended public beta

A mobile-friendly interface for asking naturally, receiving trusted travel information, editing feasible multi-day plans and visualizing routes. This demo is the first reproducible vertical slice on the path to that goal.
