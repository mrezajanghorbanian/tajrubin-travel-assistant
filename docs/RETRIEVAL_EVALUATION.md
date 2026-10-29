# Offline bilingual retrieval evaluation

Run from the repository root after installing the development dependencies:

```sh
python -m tools.evaluate_retrieval
python -m pytest tests -q
```

The evaluator uses only local Python code and the checked-in synthetic fixture
`evaluation/retrieval_bilingual_v1.json`. It calls no API or model and requires
no Harness² package. Harness² is an optional evaluation methodology only;
no external harness code is installed, imported, or executed here.

## Behavior under evaluation

The default lexical retriever remains unchanged. Enable the reviewed term
translations and city equivalences explicitly:

```python
retriever = InMemoryTravelKnowledgeRetriever(documents, bilingual_aliases=True)
```

The offline QA demo exposes the same opt-in via `--bilingual-aliases`; see
[the demo commands](DEMO.md#opt-in-persianenglish-retrieval). Its end-to-end
tests exercise Markdown ingestion, Persian/English queries, city and country
filters, result limits, source attribution and unsupported-query abstention.
The CLI integration does not change this fixture or its relevance labels.

In this mode, the city filter uses the same reviewed city equivalences as
query normalization, in both directions (`تهران` / `Tehran`, `اصفهان` /
`Isfahan` / `Esfahan`, and the other cities in `curated_aliases.py`). Unknown
city names retain exact normalized comparison. Regions, countries and
categories retain their existing filter semantics. City equivalence does not
infer a province, nearby city or misspelling.

All content terms must still match. `museum opening hours` must abstain when
the document only supports `museum`. Museum/gallery and garden/park are not
synonyms. Lexical term coverage does not prove that a document supports a
claim semantically, handles negation, or contains verified current travel facts.

## Fixture and judgments

Version 1 has 10 synthetic documents and 34 manually labeled queries (18
positive and 16 negative), split equally between English and Persian. It
includes two relevant Tehran museum documents with different text and city
languages, competing cities and categories, and a foreign-country decoy.
The relevance labels are explicit document IDs; they are never derived from
the retriever's tokenizer or aliases. Cases cover:

- Persian queries over English documents and English queries over Persian documents;
- Arabic letter variants, half-spaces, English plurals and reviewed transliterations;
- explicit city filters and city terms without a filter;
- unsupported hours/prices, wrong cities, unknown cities, unrelated concepts,
  partial term matches, category and region exclusions.

These are development regression cases, not an independent held-out benchmark.
The fixture was designed while inspecting the retriever. Perfect scores on
it do not establish real-world tourism quality or general Persian understanding.

## Metrics at k = 3

For returned IDs R and explicitly relevant IDs G:

- `returned_precision`: total relevant returned documents / total returned
  documents, over **all** cases. Negative-query false positives count against
  precision. Null when nothing was returned.
- `precision_at_k`: mean `|R intersect G| / k` over positive queries. Missing
  result slots count as zero; this is the conventional fixed-k denominator.
- `recall_at_k`: mean `|R intersect G| / |G|` over positive queries.
- `hit_at_1`: fraction of positive queries whose first result is relevant.
- `negative_abstention`: fraction of negative queries with no returned hits.

Metrics with no eligible queries are null. Successful negative abstention is
never included in positive recall. The report provides per-language metrics,
per-query IDs, fixture version and SHA-256 for reproducibility. Scores are
ranking weights, not probabilities or confidence estimates.

The tests independently hand-check the metrics with false positives, missed
relevant documents and empty results. Every bilingual fixture case must return
exactly the labeled relevant set; aggregate averages cannot hide a bad case.
Both baseline and opt-in reports are emitted so recall gains cannot conceal
negative-query regressions.

## Validation record

The starting revision `942f0a923e58e5c8bfdc71046626078a32a12a47` passed
[CI run 40762241953](https://github.com/mrezajanghorbanian/tajrubin-travel-assistant/actions/runs/40762241953):
335 tests, repository security gate, Bandit, dependency audit and secret scan.
The workflow tested GitHub's generated PR merge revision `d1b9814`, without
merging the PR. The dependency audit skipped this unpublished project package;
its installed third-party dependencies were audited.

Measured locally on the version 1 fixture:

| Metric | Default lexical | Bilingual before city fix | Bilingual after city fix |
| --- | ---: | ---: | ---: |
| Returned precision (all queries) | 100% | 100% | 100% |
| Precision@3 (positive queries) | 9.26% | 22.22% | 42.59% |
| Recall@3 (positive queries) | 19.44% | 52.78% | 100% |
| Hit@1 (positive queries) | 27.78% | 66.67% | 100% |
| Negative abstention (16 queries) | 100% | 100% | 100% |

The pre-fix bilingual measurements use revision `942f0a9` with the same
fixture. There are only one or two relevant documents per positive query,
so even perfect retrieval cannot produce Precision@3 of 100% here.

Local validation uses Python 3.12, pytest 9.1.1 and Pydantic 2.13.5;
GitHub's workflow uses Python 3.11 and resolves dependencies independently.
On Windows, `test_local_knowledge_pack_rejects_symlink` may skip when the
account cannot create symlinks. Use a writable pytest temporary directory
if the system temporary directory is restricted. These environment limits
must not be handled by weakening assertions or claiming skipped tests passed.

City-filter revision `be9661d`: local suite 353 passed, 1 skipped (the symlink
test above); all 19 new tests passed. The repository security gate, Bandit and
pip dependency consistency check passed.

The subsequent CLI integration adds 16 end-to-end tests. Local validation:
369 passed, 1 skipped (the same Windows symlink test); security gate, Bandit
and pip dependency consistency check passed. The fixed 34-case retrieval
benchmark retains the post-fix metrics above. This integration makes the
opt-in mode available in the demo; it does not claim a further recall gain.
