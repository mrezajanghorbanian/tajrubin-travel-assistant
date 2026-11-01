# Public prototype status and review map

Snapshot date: 2026-11-01. This describes the public
`planning/product-roadmap-v1` branch and [Draft PR #14](https://github.com/mrezajanghorbanian/tajrubin-travel-assistant/pull/14).
It is an evidence snapshot, not a completion percentage or launch approval.

## Verified baseline

Runtime source revision:
[`0720a562af531d9623c580984f270a7564c2d7c5`](https://github.com/mrezajanghorbanian/tajrubin-travel-assistant/commit/0720a562af531d9623c580984f270a7564c2d7c5).
[CI run 41266612574](https://github.com/mrezajanghorbanian/tajrubin-travel-assistant/actions/runs/41266612574)
completed successfully with **595 tests passed in 6.47 seconds** on Python 3.11.
The workflow runs against GitHub's generated PR merge revision; this does not
mean the PR was merged into `main`.

All five offline retrieval gates, the repository security gate, Bandit,
dependency audit and working-tree secret scan passed. The dependency audit
reported no known vulnerabilities in the audited installed dependencies.
These automated checks do not establish an independent security review,
historical secret audit, production hardening or complete tourism accuracy.

The corresponding local Windows validation recorded 594 passed and one
symlink-privilege skip. Linux CI passed that test. Counts are tied to the
revision above and must be refreshed after executable changes.

## What can be run today

After installing the project and development dependencies from the repository:

```sh
python -m pip install -e ".[dev]"
python -X utf8 -m app.assistant 'لطفاً درباره کاخ گلستان' --format json
python -X utf8 -m app.assistant 'برای ۳ روز تهران برنامه سفر میخواهم' --format json
python -m pytest tests -q
```

The first request returns a stored, source-attributed provisional summary.
The second returns resolved initial planning inputs, not an itinerary.
Neither command requires a model, paid API, provider account or signing key.
The development dependency group includes signing dependencies for the full
test suite; the unified assistant entry point does not require their imports.
The interface keeps `live_verified=false` and `needs_verification=true`.
See [local assistant behavior](LOCAL_ASSISTANT.md).

## Implemented slices and their limits

| Slice | Available behavior | Remaining boundary |
| --- | --- | --- |
| Grounded local QA | Bounded typed requests, local Markdown ingestion, source IDs/URLs/review dates, explicit abstention | Stored summaries and lexical evidence coverage do not prove semantic support or current visitor facts |
| Persian/English retrieval | Opt-in reviewed term and city equivalents, limited plurals, exact query wrappers, strict term coverage and filters | Small reviewed vocabulary; no semantic model, general Persian grammar or broad translation |
| Iran knowledge | Four Markdown records: Tehran overview plus Golestan, Isfahan Jame Mosque and historic Yazd | Only three records have UNESCO source references; these short notes provide no current hours, prices or routing evidence |
| Intent and readiness | Conservative English/Persian extraction and clarification for initial trip details | No conversation memory; ambiguous language and unsupported locations remain limited |
| Scheduler and trip preview | Separate deterministic scheduling over selected activities with supplied dated windows and directed travel times | No autonomous attraction selection, verified routing provider or live attraction inventory; a signed catalog does not make facts true |
| Catalog and release libraries | Local catalog/review storage, externally verified identity boundary, signed releases and persistent sequence checks | Trusted-process prototypes; deployment authentication, key custody, protected persistence and cross-service consistency require separate work |

Scheduling and release primitives are distinct from the unified QA/readiness
command. Their synthetic test fixtures are not real visitor data. References:
[trip preview](TRIP_PREVIEW.md), [scheduler](ITINERARY_SCHEDULER.md),
[catalog](CATALOG_REPOSITORY.md), [authorization](AUTHORIZATION_AND_RELEASE.md),
[signed releases](SIGNED_RELEASE.md) and [persistent release state](RELEASE_STATE.md).

## Reproducible retrieval evidence

```sh
python -m tools.evaluate_retrieval --suite bilingual --check
python -m tools.evaluate_retrieval --suite persian-plurals --check
python -m tools.evaluate_retrieval --suite palace-mosque --check
python -m tools.evaluate_retrieval --suite persian-query-wrappers --check
python -m tools.evaluate_knowledge_pack --check
```

The first four gates contain 34, 28, 28 and 30 synthetic development queries.
The fifth evaluates 32 manual development judgments against the actual
Markdown corpus, with a separate corpus fingerprint. These are regression
cases designed with knowledge of the implementation, not independent held-out
benchmarks. Each gate checks individual bilingual results; negative abstention
is reported separately from positive recall. The default lexical comparison
may fail the exact gold gate without making the opt-in bilingual gate fail.
Metric denominators, before/after results and limitations are documented in
[retrieval evaluation](RETRIEVAL_EVALUATION.md).

## Milestone interpretation and next review boundary

- M0 has recorded automated CI evidence. Human review and owner decisions
  remain separate; passing CI does not complete the milestone by itself.
- M1 has a runnable QA/readiness slice, a very small sourced knowledge pack
  and development regression gates. Broader knowledge coverage and independent
  product-quality evaluation remain open.
- M2 has scheduling and evidence-checking primitives tested with supplied
  data. An automatic, realistic traveler itinerary is not delivered by the
  unified command.
- M3 through M5 are roadmap targets: a public mobile web journey, map/edit
  flow, production observability and live onboarding have not been verified
  by this branch's Python CI.

PR #14 contains several subsystems and requires review across the boundaries
above. Its Draft state and the instruction not to merge into `main` remain in
force. The private Tajrubin backend, secrets and private data stay outside this
work. Harness² remains an optional evaluation method, not a runtime dependency.
