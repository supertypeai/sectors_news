#!/usr/bin/env bash
set -euo pipefail

fail() { echo "preflight: $*" >&2; exit 1; }

for name in SUPABASE_URL SUPABASE_KEY OPENROUTER_API_KEY GROQ_API_KEY_DEV PROXY; do
    [ -n "${!name:-}" ] || fail "$name is empty — set it at /deploy, the key icon on sectors_news"
done

# The venv lives in the image, the code in the checkout.
cmp -s /opt/uv.lock uv.lock || fail "uv.lock changed since the image was built; rebuild it (.dagu/README.md)"

command -v google-chrome >/dev/null || fail "google-chrome is not on PATH"

# Chrome dies partway through a page on the container default of 64 MiB, not at startup.
shm_mb=$(( $(df -k /dev/shm | awk 'NR==2 {print $2}') / 1024 ))
[ "$shm_mb" -ge 256 ] || fail "/dev/shm is ${shm_mb} MiB; the host mount did not take"

python -c 'import scraper_engine.pipeline' || fail "cannot import scraper_engine (traceback above)"

echo "preflight ok: $MARKET @ $(git rev-parse --short HEAD), $(google-chrome --version), /dev/shm ${shm_mb} MiB"
