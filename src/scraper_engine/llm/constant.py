MODEL_NAMES = [
    "gpt-oss-120b",
    "nvidia-nemotron-3-ultra",
    "gpt-oss-20b",
    "llama-3.3-70b",
    "kimi-k2",
]

MODEL_CONFIG = {
    "kimi-k2": {
        "model": "moonshotai/kimi-k2-instruct-0905",
        "provider": "groq",
    },
    "gpt-oss-120b": {
        "model": "openai/gpt-oss-120b",
        "provider": "groq",
    },
    "gpt-oss-20b": {
        "model": "openai/gpt-oss-20b",
        "provider": "groq",
    },
    "llama-3.3-70b": {
        "model": "llama-3.3-70b-versatile",
        "provider": "groq",
    },
    "nvidia-nemotron-3-ultra": {
        "model": "nvidia/nemotron-3-ultra-550b-a55b:free",
        "provider": "openrouter",
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
