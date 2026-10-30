# Public Iran knowledge pack

The offline demo loads the Markdown records in `knowledge/iran/`. The pack
now contains the original Tehran overview and three short, bilingual records
with public source references.

| Record | City / category | Source reviewed on 2026-10-29 |
| --- | --- | --- |
| `ir.tehran.golestan-palace` | Tehran / attraction | [UNESCO: Golestan Palace](https://whc.unesco.org/en/list/1422/) |
| `ir.isfahan.jame-mosque` | Isfahan / attraction | [UNESCO: Masjed-e Jāmé of Isfahan](https://whc.unesco.org/en/list/1397/) |
| `ir.yazd.historic-city` | Yazd / destination | [UNESCO: Historic City of Yazd](https://whc.unesco.org/en/list/1544/) |

Each new record carries the source publisher, URL, access date, review date,
city and category. Its short English and Persian notes cover historical or
architectural facts from the cited page. The mosque record includes an
explicit unaccented search spelling, `Masjed-e Jame`, alongside its accented
name. Sources are read during content review; the demo does not fetch them.

## Run locally

```sh
python -X utf8 -m app.assistant.demo 'کاخ گلستان' --country IR --city تهران --bilingual-aliases --format json
python -X utf8 -m app.assistant.demo 'Masjed-e Jame' --country IR --city Isfahan --bilingual-aliases --format json
python -X utf8 -m app.assistant.demo 'شهر تاریخی یزد' --country IR --city یزد --bilingual-aliases --format json
```

Each command returns the matching document ID, review date and official
source URL with `status=provisional` and `needs_verification=true`.

## Evidence limits

This pack supplies bounded background knowledge. Source-page review dates
record when the text was checked; they do not verify visitor access today.
The records provide no opening windows, admission prices, travel times,
visit durations, booking inventory or accessibility certification. Queries
requiring those missing details must abstain.

These knowledge records do not become approved scheduler inputs simply by
having a source URL. The separate attraction-catalog, editorial-review and
signed-release requirements in [the trip preview](TRIP_PREVIEW.md) still apply.
The original `ir.tehran.destination` overview retains its empty source list;
the new citations do not retroactively verify that older record.

The source descriptions and their licensing information remain available on
the linked UNESCO pages. This addition supplies short factual notes and source
metadata; it adds no source images or project-wide license file.

## Validation

`python -m pytest tests/test_public_iran_knowledge_pack.py -q` checks named
retrieval in both languages, the explicit spelling variant, source propagation,
city/country/category exclusions and unsupported live-information requests.
These tests run fully offline and do not establish broad retrieval quality.
The two frozen synthetic evaluation suites remain unchanged.

Local validation: 480 passed, 1 Windows symlink skip; all 23 new pack tests passed. Both frozen synthetic suite gates, the repository security gate, Bandit and pip dependency consistency check passed.
