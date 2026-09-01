#!/bin/bash

PROJECT="datasheet-398802"
PROJECT_NUMBER="607838700058"
REGION="us-central1"
REPO="cloud-run-source-deploy"
BUCKET="sectors-news-pipeline-state"
SA_NAME="sectors-news-pipeline"
SA="${SA_NAME}@${PROJECT}.iam.gserviceaccount.com"

# Cloud Scheduler triggers the jobs as this identity. The default compute
# account already holds roles/editor, which includes run.jobs.run — so it can
# invoke without a roles/run.invoker binding, which nobody here has the
# permission to grant.
SCHEDULER_SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"
# Exactly what scraper_engine.config.conf demands via get_required_env(), which
# raises at import — a missing one fails the run before it scrapes anything.
# Keep in step with `grep get_required_env src/scraper_engine/config/conf.py`.
SECRETS=(
    SUPABASE_URL
    SUPABASE_KEY
    OPENROUTER_API_KEY
    GROQ_API_KEY_DEV
    PROXY
)

# Writes the --env-vars-file a deploy hands to Cloud Run: the runtime config
# passed as arguments, plus the values above read out of ENV_FILE (default .env
# at the repo root). --env-vars-file replaces the whole environment, so both
# halves have to be in the one file.
#
# A file rather than --set-env-vars because the values are secrets: command-line
# arguments are visible to `ps` for every user on the machine, and a value
# containing a comma would silently split. Values are YAML double-quoted with
# backslashes and quotes escaped, so a proxy password with punctuation survives.
#
# usage: write_env_file <dest> <KEY=VALUE>...
write_env_file() {
    local dest="$1"; shift
    local source_env="${ENV_FILE:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)/.env}"

    if [[ ! -f "$source_env" ]]; then
        echo "No ${source_env} to read values from." >&2
        return 1
    fi

    : >"$dest"
    chmod 600 "$dest"

    local pair
    for pair in "$@"; do
        printf '%s: "%s"\n' "${pair%%=*}" "${pair#*=}" >>"$dest"
    done

    local key value missing=0
    for key in "${SECRETS[@]}"; do
        value="$(grep -E "^${key}=" "$source_env" | head -n1 | cut -d= -f2-)"

        # Trim surrounding whitespace before unquoting, the way python-dotenv
        # does. Without this a stray trailing space in .env reaches the
        # container intact and an API key becomes an "Illegal header value" —
        # while everything keeps working locally, because load_dotenv() strips
        # it. That asymmetry is the whole reason this is here.
        value="${value#"${value%%[![:space:]]*}"}"
        value="${value%"${value##*[![:space:]]}"}"

        value="${value%\"}"; value="${value#\"}"
        value="${value%\'}"; value="${value#\'}"
        value="${value#"${value%%[![:space:]]*}"}"
        value="${value%"${value##*[![:space:]]}"}"

        if [[ -z "$value" ]]; then
            echo "  ! ${key} is empty or absent in ${source_env}" >&2
            missing=1
            continue
        fi

        value="${value//\\/\\\\}"   # backslashes first,
        value="${value//\"/\\\"}"   # then quotes
        printf '%s: "%s"\n' "$key" "$value" >>"$dest"
    done

    return "$missing"
}
