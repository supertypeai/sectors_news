MODEL_NAMES = [
    "gpt-oss-120b",
    "deepsek-v4-flash",
    "gpt-oss-20b",
    "nvidia-nemotron-3-ultra",
]

MODEL_CONFIG = {
    "gpt-oss-120b": {
        "model": "openai/gpt-oss-120b",
        "provider": "groq",
        "max_tokens": 65536
    },
    "deepsek-v4-flash": {
        "model": "deepseek/deepseek-v4-flash-0731",
        "provider": "openrouter",
    },
    "gpt-oss-20b": {
        "model": "openai/gpt-oss-20b",
        "provider": "groq",
    },
    "nvidia-nemotron-3-ultra": {
        "model": "nvidia/nemotron-3-ultra-550b-a55b",
        "provider": "openrouter",
        "max_tokens": 16000,
    },
    "glm-5.3-flash": {
        "model": "z-ai/glm-5.3-flash",
        "provider": "openrouter"
    }
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
