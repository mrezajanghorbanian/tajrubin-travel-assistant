# CORE-01: real local-model intake turn

The first model-connected entry point reuses the existing local runtime
configuration and OpenAI-compatible generation adapter. It makes one bounded
inference and validates a Persian intake draft. This is the first connection
checkpoint, not a complete conversational travel agent.

## Run against the existing model

With the installed local server and model ready:

```sh
python -X utf8 -m app.assistant.local_model_turn 'برای سه روز شیراز یه سفر آروم می‌خوام.' --format json
```

Defaults reuse `qwen3.5-4b` at `http://127.0.0.1:1234`; no API key is required
by this command. `--model` can name an already available local model and
`--base-url` can select another validated loopback server root. This does not
install/download a model or activate a paid service. The older
`python -m app.assistant` command retains its deterministic behavior.

For the existing LM Studio installation, inspect `lms ps` and `lms ls --llm`.
The following uses an already installed model and binds the server locally:

```sh
lms load qwen3.5-4b --identifier qwen3.5-4b --context-length 2048 --gpu off --ttl 3600 --yes
lms server start --port 1234 --bind 127.0.0.1
```

CPU mode is a diagnostic configuration used in the recorded local checks,
not a universal performance recommendation. Do not change or unload another
user's active model to run this command. See the official
[load command](https://lmstudio.ai/docs/cli/local-models/load) for its options.

## Contract and failure behavior

The request is a 3–2000-character message, with a strict integer output budget
of 128–1024 tokens (default 512). CLI timeout is greater than zero and at most
120 seconds (default 120). There is one request and no automatic retry.

The application sends the intake JSON Schema through the provider's optional
`response_schema_json` request field and the server's `response_format`.
Legacy generation requests omit that option and retain their existing shape.
See [LM Studio structured output](https://lmstudio.ai/docs/developer/openai-compat/structured-output).
The returned content is validated again locally; server format enforcement
does not establish semantic correctness. The model must return exactly these
two JSON keys:

```json
{
  "understanding": "خلاصه فارسی خواسته‌های صریح کاربر",
  "clarification_question": "یک سؤال ضروری یا مقدار JSON null"
}
```

`understanding` is nonblank and at most 2000 characters; the question is null
or a nonblank string of at most 500 characters. Unknown/action-bearing keys,
duplicate keys, malformed or excessively nested JSON and output above 8000
characters are rejected. Markdown fences and partial JSON are not silently
repaired. A valid schema does not prove that the model's interpretation or
question is semantically correct.

The returned envelope contains one of:

| Status | Payload | Meaning |
| --- | --- | --- |
| `model_reply` | `intake` and model label | The generation adapter returned a schema-valid draft; this is not a completed plan |
| `model_unavailable` | Bounded error code, no intake | Timeout, transport or HTTP failure; no rule-only answer is substituted |
| `invalid_model_reply` | Bounded error code, no intake | Invalid provider response or output contract; no generated action is executed |

The model label is reported by the server, falling back to the configured
label when omitted; it is not cryptographic proof of model weights.
`live_verified=false` and `needs_verification=true` remain mandatory.
CLI exits 0 for a valid model draft, 1 for model/service/output failure, and
2 for invalid input/configuration. Errors do not expose raw provider messages
or echo invalid user input.

The local builder disables environment proxies and HTTP redirects. Base URLs
must be loopback roots without embedded credentials, paths, queries or
fragments. The general generation adapter retains its existing proxy default
for non-local callers. No shell tools, browsing, booking or signed-catalog
operations are exposed to this model turn.

## Verification boundaries

```sh
python -m pytest tests/test_local_model_turn.py -q
python -m pytest tests -q
```

CI uses synthetic responses through the actual HTTP adapter boundary and
checks request roles/budgets, strict output validation, provider failures,
CLI exit codes and local configuration. CI does not contact LM Studio or
prove inference quality. The application writes no session/history files;
the separately managed model server has its own logging behavior.

Local real-model checks use only synthetic traveler input. Initial attempts
with automatic GPU settings included a 60-second timeout and a later HTTP
failure after the model left memory. A valid draft also took 88.98 seconds
and omitted a needed date question. These observations are not a latency
benchmark or evidence of reliable conversational behavior. CPU mode and a
clearer Persian instruction are checked separately; do not hide earlier
failures behind CI success.

### Recorded real inference, 2026-11-03

With the existing Qwen3.5-4B model loaded on CPU, context length 2048 and
schema-constrained output, two independent synthetic-input checks succeeded:

| Application path | Input | Observation |
| --- | --- | --- |
| `generate_local_turn` | «برای سه روز شیراز یه سفر آروم می‌خوام.» | Persian summary retained Shiraz, three days and relaxed travel; asked for travel dates; 15.11 seconds |
| Actual module CLI | «برای دو روز تهران با دو نفر یه سفر کم‌هزینه می‌خوام.» | Persian summary retained Tehran, two days, two people and low budget; asked for travel dates; exit 0; 18.56 seconds |

The [public evidence record](evidence/core01-local-model-2026-11-03.json)
contains only these synthetic inputs, model outputs and bounded runtime
settings. No private traveler information or credentials were used. The
second input was a new independent turn, not proof of session memory.
Timings are observations under the local workload, not an SLO or benchmark.
CPU success does not establish the root cause of earlier runtime failures.

Local final automated validation: 707 passed, one Windows symlink skip;
46 new model-turn/schema cases passed. Repository security gate, Bandit and
dependency consistency checks passed. These counts are separate from real
inference evidence; hosted CI must be checked on the published revision.

CORE-02 still needs session continuity; CORE-03 needs grounded tools;
CORE-04/05 need an initial plan and an in-chat edit. A single successful
Persian turn does not complete those stages or the active sprint.
