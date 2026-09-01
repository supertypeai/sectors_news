# Fallback order. Groq first (it is on our own key), OpenRouter last as the
# backstop when Groq rate-limits — there is only one Groq key now, so that
# happens more often than it used to.
#
# Every entry below has been checked against the live provider. Two that used to
# be here were removed because Groq no longer serves them at all:
# moonshotai/kimi-k2-instruct-0905 and llama-3.3-70b-versatile both returned
# "model does not exist", burning a rotation slot on every article.
#
# Nothing else Groq serves on this account is usable as a fourth:
#   qwen/qwen3.6-27b  rejects reasoning effort "high" (get_llm passes it to every
#                     model and no caller overrides it), so it needs per-model
#                     effort in MODEL_CONFIG before it could be added.
#   qwen/qwen3.8-27b  works, but is rate-limited to 8,000 TPM against 250,000 for
#                     the gpt-oss models — a single article summarisation exceeds
#                     it, so it 413s on nearly every call.
#   gpt-oss-safeguard-20b, llama-prompt-guard-*  safety classifiers, wrong tool.
#   groq/compound*    agentic systems, not plain chat models.
MODEL_NAMES = [
    "gpt-oss-120b",
    "gpt-oss-20b",
    "nvidia-nemotron-3-ultra",
]

MODEL_CONFIG = {
    "gpt-oss-120b": {
        "model": "openai/gpt-oss-120b",
        "provider": "groq",
    },
    "gpt-oss-20b": {
        "model": "openai/gpt-oss-20b",
        "provider": "groq",
    },
    # Not the ":free" variant. That suffix routes to the queued free tier, where
    # a call with effort=high and a 16k budget took 462s and hit a read timeout;
    # the paid endpoint answers the same prompt in ~2s, and this key is paid.
    "nvidia-nemotron-3-ultra": {
        "model": "nvidia/nemotron-3-ultra-550b-a55b",
        "provider": "openrouter",
        "max_tokens": 16000,
    },
}

ROTATE_STATUS_CODES = {401, 403, 429, 413}
ABORT_STATUS_CODES = {400, 422, 500, 502, 503, 504}

ROTATE_KEYWORDS = (
    "rate limit",
    "too many requests",
    "authentication",
    "invalid api key",
    "request too large",
)
ROTATE_400_KEYWORDS = ("organization_restricted",)
ABORT_KEYWORDS = (
    "context length",
    "max token",
    "internal server",
    "bad gateway",
    "service unavailable",
)
