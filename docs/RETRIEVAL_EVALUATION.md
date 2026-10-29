# Offline bilingual retrieval evaluation

Run from the repository root after installing the development dependencies:

```sh
python -m tools.evaluate_retrieval
python -m tools.evaluate_retrieval --k 1
python -m tools.evaluate_retrieval --k 5
python -m pytest tests -q
```

The evaluator uses only local Python code and the checked-in synthetic suites.
Its default fixture is `evaluation/retrieval_bilingual_v1.json`. It calls no API or model and requires
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

## Attached Persian plural suite

```sh
python -m tools.evaluate_retrieval --suite persian-plurals
python -m pytest tests/test_attached_persian_plurals.py -q
```

`evaluation/retrieval_persian_plurals_v1.json` is a separate development suite
with 8 synthetic documents, 12 positive queries and 16 negative queries.
It preserves the original 34-case suite and its relevance labels. Reports
include the selected suite name, fixture version and fixture hash.

Opt-in bilingual retrieval recognizes eight exact attached plural forms:
`موزهها`, `موزههای`, `باغها`, `باغهای`, `رستورانها`, `رستورانهای`, `بازارها`
and `بازارهای`. These forms map to the existing singular travel concepts on
both query and document sides. There is no general Persian suffix stripping;
`باغبان`, `باغچه`, `رستوراندار`, `بازاریابی` and other unlisted forms remain
distinct. Unknown qualifiers and city constraints remain required.

| Metric | Before plural aliases (`7b61c19`, bilingual) | After plural aliases (bilingual) |
| --- | ---: | ---: |
| Returned precision | 100% | 100% |
| Precision@3 | 22.22% | 66.67% |
| Recall@3 | 33.33% | 100% |
| Hit@1 | 66.67% | 100% |
| Negative abstention (16 queries) | 100% | 100% |

Every positive query labels two documents as relevant, so perfect retrieval
has Precision@3 of 2/3. The unchanged default lexical mode retains Recall@3
of 1/3 on this suite. The original bilingual suite retains its prior post-fix
metrics. Both suites are synthetic development regressions, not independent
held-out evidence of general Persian language quality.

## Metrics at the selected k (default 3)

`--k` accepts integers from 1 through 20, matching the retriever contract.
It controls both the actual number requested from each retriever and the
metric cutoff. The default remains 3. The offline QA demo independently
limits `--max-results` to 1 through 5.

For the first k returned IDs R and explicitly relevant IDs G:

- `returned_precision`: total relevant returned documents / total returned
  documents, over **all** cases. Negative-query false positives count against
  precision. Null when nothing was returned.
- `precision_at_k`: mean `|R intersect G| / k` over positive queries. Missing
  result slots count as zero; this is the conventional fixed-k denominator.
- `recall_at_k`: mean `|R intersect G| / |G|` over positive queries.
- `hit_at_1`: fraction of positive queries whose first result is relevant.
- `mrr_at_k`: mean reciprocal rank of the first relevant result within the
  first k results, over positive queries. A positive query with no relevant
  result contributes zero. No positive queries means null.
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

### Cutoff comparison on the fixed synthetic suites

| Suite (bilingual mode) | k | Precision@k | Recall@k |
| --- | ---: | ---: | ---: |
| Original bilingual | 1 | 100% | 86.11% |
| Original bilingual | 3 | 42.59% | 100% |
| Original bilingual | 5 | 25.56% | 100% |
| Attached Persian plurals | 1 | 100% | 50% |
| Attached Persian plurals | 3 | 66.67% | 100% |
| Attached Persian plurals | 5 | 40% | 100% |

Returned precision, MRR@k and negative abstention are 100% in these six runs.
Lower fixed-denominator Precision@k at larger k reflects unfilled slots here;
it does not mean the retriever returned extra incorrect documents. Recall
at k=1 exposes missed relevant documents that Recall@3 conceals. Equal
relevance labels do not judge ordering among two relevant documents.

The summarizer itself truncates supplied result lists at k, even if an
external caller supplies more results; it does not mutate the caller's data.
Previously it relied on the caller's result limit, so a list longer than k
could inflate Precision@k above 1. Hand-counted tests include irrelevant
results before and after the cutoff, a relevant result at rank 2, missing
positive results and negative queries. This evaluator correction and the new
MRR field do not change either knowledge fixture or the retrieval algorithm.

## Per-case synthetic CI gate

```sh
python -m tools.evaluate_retrieval --suite bilingual --check
python -m tools.evaluate_retrieval --suite persian-plurals --check
```

Both commands run in the security workflow after pytest. The JSON report is
printed in the Actions log, including fixture hash, per-language metrics and
the gate result. No additional action, dependency or external runtime is used.

Every report includes a `gate` section for each retriever mode, under policy
`exact_synthetic_relevance_at_k_v1`. `--check` returns exit code 1 when the
**bilingual** gate fails, and 0 when it passes. The weaker default retriever
is reported as a comparison and does not determine this exit code. Without
`--check`, the tool remains report-only and exits 0 after successful evaluation,
even when the gate reports a retrieval failure. Invalid arguments exit 2.

For every query, the gate requires:

- no unexpected document IDs within the first k results;
- at least `min(k, number of relevant IDs)` distinct relevant results;
- no duplicate returned IDs or result count above k;
- no results for a negative query.

An empty case set fails. Each failure includes its `case_id`, unexpected IDs,
the number of required relevant results missing, duplicate IDs and an
over-limit flag. At k=1, returning one of two equally relevant documents is
valid; the report still exposes Recall@1 of 50% for that query. A high aggregate
average cannot hide an individual failed case.

Tests cover controlled wrong judgments and an actual retrieval regression:
aliases are removed only in a child process, the real module is run against
unchanged labels, and its nonzero exit and failure report are verified.
This is a strict gate for these synthetic development suites, not a production
readiness claim or an independent held-out benchmark. Fixture changes require
review of their relevance labels; passing a modified fixture alone is not
evidence that retrieval improved.

## Fixture integrity before scoring

Both modes validate the fixture before retrieval. Only version 1 and an
explicit JSON `synthetic: true` are accepted; numeric 1 is not interchangeable
with a boolean version. Unknown top-level or case fields are rejected.

Each fixture requires 1–500 schema-valid documents and 2–2000 cases, including
at least one positive and one negative query. Document IDs and case IDs must
be unique; case IDs must be nonblank and at most 160 characters. Language
labels must be `en` or `fa`. Queries must satisfy `RetrievalQueryV1` and cannot
override the evaluation cutoff with their own `limit`.

Relevant-ID lists must contain unique existing document IDs. In particular,
at k=1 a valid hit must not hide a second relevant label that points to a
nonexistent document. Label validation is structural: the evaluator does not
generate or revise relevance judgments using its own matching logic. It still
cannot determine whether a human's semantic relevance judgment is correct.

Unreadable files, invalid JSON or invalid fixture structure return exit code 2
and a JSON error with code `invalid_fixture`, without success metrics. This
applies both with and without `--check`. A structurally valid fixture whose
retrieval fails the gate continues to return exit code 1 only with `--check`.
The original frozen fixture files and their labels remain unchanged.

## Validation history

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

Attached-plural integration local validation: 401 passed, 1 skipped (the same Windows symlink test); all 32 new tests passed. Repository security gate, Bandit and pip dependency consistency check passed.

Cutoff/MRR evaluation local validation: 423 passed, 1 skipped (the same Windows symlink test); all 22 new tests passed. Repository security gate, Bandit and pip dependency consistency check passed.

Synthetic gate integration local validation: 436 passed, 1 skipped (the same Windows symlink test); all 13 new tests passed. Both suite gates passed at k=1,3,5. Repository security gate, Bandit and pip dependency consistency check passed.

Fixture-integrity local validation: 457 passed, 1 skipped (the same Windows symlink test); all 21 new tests passed. Both original suite gates passed with unchanged fixture files. Repository security gate, Bandit and pip dependency consistency check passed.
