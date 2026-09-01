# Model changes and reasoning

2026-09-01. Context: `1ddebc7 refactor(llm)` moved the pipeline to OpenRouter but
never updated `pyproject.toml`. No CI run ever executed it — the first thing that
did was the new Cloud Run job, which scraped normally and inserted **0 rows**.

## 1. Dependencies

The refactor's code needed newer libraries than the lockfile pinned.

| package | was | now | why |
| --- | --- | --- | --- |
| `langchain` | 0.3.27 | 1.3.18 | 0.3 doesn't know `model_provider="openrouter"` |
| `langchain-groq` | 0.3.6 | 1.1.3 | 0.3.6 rejects `reasoning_effort="high"` |
| `langchain-openrouter` | — | 0.2.8 | separate package; langchain 1.x only names the provider, this implements it |
| `openai` | ==1.93.3 | >=1.99.9 | floor required by langchain 1.x; nothing imports it directly |

Observed before the fix:

```
ChatGroq: reasoning_effort — Input should be 'none' or 'default', got 'high'
Unsupported model_provider='openrouter'
```

**Side effect:** langchain 1.x removes `langchain.prompts`. Five files moved to
`langchain_core.prompts` — `scorer.py`, `classifier.py`, `summarizer.py`,
`company_extractor.py`, `update_existing_tags.py`. Import only, no behaviour change.

## 2. Model rotation

Three of the five configured models could not work at all.

| model | verdict | reason |
| --- | --- | --- |
| `openai/gpt-oss-120b` | **kept** | 250,000 TPM |
| `openai/gpt-oss-20b` | **kept** | 250,000 TPM |
| `nvidia/nemotron-3-ultra-550b-a55b` | **kept, moved last** | see §3 |
| `moonshotai/kimi-k2-instruct-0905` | **removed** | Groq: "model does not exist" |
| `llama-3.3-70b-versatile` | **removed** | Groq: "model does not exist" |

The two dead entries burned a rotation slot on every article — 12 wasted calls in
one 22-article run.

**Nothing else on this Groq account is a usable fourth:**

- `qwen/qwen3.6-27b` → rejects `reasoning_effort="high"`, which `get_llm` passes
  to every model with no caller override. Would need per-model effort first.
- `qwen/qwen3.8-27b` → works standalone, but **8,000 TPM vs 250,000**. One article
  summarisation exceeds it, so it 413s on nearly every real call.
- `gpt-oss-safeguard-20b`, `llama-prompt-guard-*` → safety classifiers, wrong tool.
- `groq/compound*` → agentic systems, not plain chat models.

**Ordering:** Groq first (our own key, generous limits), OpenRouter last as the
backstop. An earlier concern that one Groq key would rate-limit constantly was
wrong — 250,000 TPM / 500,000 RPM is ample. The old 5-key rotation was
compensating for something that is not a constraint here.

## 3. Dropped the `:free` suffix

`nvidia/nemotron-3-ultra-550b-a55b:free` → `nvidia/nemotron-3-ultra-550b-a55b`.

| endpoint | same prompt |
| --- | --- |
| `:free` (queued tier) | 29.6 s raw; **462 s then ReadTimeout** with `effort=high` + 16k budget |
| paid | **~2 s** |

The OpenRouter key is paid (`is_free_tier: false`), so `:free` bought queueing
and nothing else. It sat *second* in the rotation, so it was the first fallback
on every Groq failure.

## 4. `max_tokens` moved into `MODEL_CONFIG`

Was `16000 if model_name == "nvidia-nemotron-3-ultra" else 25000` — a hardcoded
special case. Providers cap this differently and exceeding it is a hard 400, so
the limit now lives beside the model it belongs to:

```python
"max_tokens": config_model.get("max_tokens", 25000)
```

Only entries that differ from the 25000 default need the key.

## Verified

All three models constructed **and invoked live**, returning valid JSON:

| model | provider | latency |
| --- | --- | --- |
| `gpt-oss-120b` | groq | 0.9 s |
| `gpt-oss-20b` | groq | 0.6 s |
| `nvidia-nemotron-3-ultra` | openrouter | 2.4 s |

## Still open

- **13× `Invalid json output`** in the last run — models returning malformed JSON
  to `JsonOutputParser`. Pre-existing, not addressed here.
- **No request timeout.** A hung provider blocks a run for as long as it likes;
  the `:free` endpoint burned 462 s before giving up. Cloud Run bills wall-clock.
- **Single Groq key.** Fine at current limits, but `KeyRotatingChatModel` has
  nothing to rotate to if that key is revoked or rate-limited.

## Commits

```
f302e44  fix(llm): drop unavailable models, use paid nemotron endpoint, per-model max_tokens
979ad02  fix(deps): upgrade langchain to 1.x and add langchain-openrouter
```
