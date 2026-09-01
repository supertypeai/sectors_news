#!/bin/bash
# Look at what the pipelines remember.
#
# On GitHub Actions you could see the pipeline's memory by opening the repo.
# The bucket is tidier but invisible, so this is the replacement for "just look
# at it". Read-only — nothing here writes to the bucket.
#
#   ./state.sh                    both pipelines, at a glance
#   ./state.sh idx                one pipeline, in full
#   ./state.sh idx runs           recently archived runs
#   ./state.sh idx get <file>     print one file from the live state
#   ./state.sh idx get <file> --run <id>    ... from an archived run instead
#
# Examples:
#   ./state.sh sgx
#   ./state.sh idx get last_state.json
#   ./state.sh idx get idx/pipeline_filtered.json
#   ./state.sh idx get last_state.json --run 20260901T072003Z
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${HERE}/config.sh"

BOLD=$'\033[1m'; DIM=$'\033[2m'; RESET=$'\033[0m'
[[ -t 1 ]] || { BOLD=""; DIM=""; RESET=""; }

usage() {
    # The header comment block, minus the shebang — stops at the first line that
    # is not a comment, so editing the block above never breaks --help.
    awk 'NR > 1 { if (!/^#/) exit; sub(/^# ?/, ""); print }' "${BASH_SOURCE[0]}"
    exit "${1:-0}"
}

# Print a file from the bucket, or nothing if it is not there. `gcloud storage
# cat` writes its own error to stderr, which we swallow: a missing object is an
# expected state here (a pipeline that has not run yet), not a failure.
fetch() {
    gcloud storage cat "gs://${BUCKET}/$1" --project "$PROJECT" 2>/dev/null
}

# Length of a JSON array, or "-" if the file is missing or not an array.
json_len() {
    fetch "$1" | python3 -c '
import json, sys
try:
    data = json.load(sys.stdin)
    print(len(data) if isinstance(data, list) else "-")
except Exception:
    print("-")
' 2>/dev/null
}

# "2026-09-01T14:15:03+07:00  (4 hours ago)" from last_state.json.
watermark() {
    fetch "$1" | python3 -c '
import json, sys
from datetime import datetime, timezone

try:
    stamp = json.load(sys.stdin)["last_run_at"]
except Exception:
    print("- (never scraped)")
    sys.exit()

moment = datetime.fromisoformat(stamp)
if moment.tzinfo is None:
    moment = moment.replace(tzinfo=timezone.utc)

seconds = (datetime.now(timezone.utc) - moment).total_seconds()
if seconds < 0:
    ago = "in the future?"
elif seconds < 3600:
    ago = f"{int(seconds // 60)} min ago"
elif seconds < 86400:
    ago = f"{seconds / 3600:.1f} hours ago"
else:
    ago = f"{seconds / 86400:.1f} days ago"

print(f"{stamp}  ({ago})")
' 2>/dev/null
}

# One `ls -l` for the whole prefix, reused for every size and timestamp below.
listing() {
    gcloud storage ls -l --recursive "gs://${BUCKET}/$1/data/**" \
        --project "$PROJECT" 2>/dev/null
}

# size + last-modified for one object, pulled out of the listing above.
detail() {
    printf '%s\n' "$2" | python3 -c '
import sys
target = sys.argv[1]
for line in sys.stdin:
    parts = line.split()
    if len(parts) >= 3 and parts[2].endswith("/" + target):
        size = int(parts[0])
        unit = "B"
        for step in ("KiB", "MiB"):
            if size >= 1024:
                size /= 1024
                unit = step
        stamp = parts[1].replace("T", " ").replace("Z", "")
        print(f"{size:.0f} {unit:<4} {stamp}")
        break
else:
    print("-")
' "$1" 2>/dev/null
}

require_bucket() {
    gcloud storage buckets describe "gs://${BUCKET}" --project "$PROJECT" >/dev/null 2>&1 && return
    echo "No bucket gs://${BUCKET} in project ${PROJECT}." >&2
    echo "Run deployments/common/bootstrap.sh first." >&2
    exit 1
}

summary() {
    local source="$1" full="$2"
    local files stamp

    files="$(listing "$source")"

    if [[ -z "$files" ]]; then
        echo "${BOLD}${source^^}${RESET}  ${DIM}gs://${BUCKET}/${source}/${RESET}"
        echo "  ${DIM}nothing stored yet — this pipeline has not completed a run${RESET}"
        echo
        return
    fi

    # data/idx/pipeline.json for idx, data/sgx/pipeline_sgx.json for sgx.
    local base="pipeline" ; [[ "$source" == "sgx" ]] && base="pipeline_sgx"
    local state="last_state.json" ; [[ "$source" == "sgx" ]] && state="last_state_sgx.json"
    local pruned="outdated_news.json" ; [[ "$source" == "sgx" ]] && pruned="outdated_news_sgx.json"

    echo "${BOLD}${source^^}${RESET}  ${DIM}gs://${BUCKET}/${source}/${RESET}"
    printf '  %-14s %s\n' "watermark" "$(watermark "${source}/data/${state}")"
    printf '  %-14s %s articles   %s%s%s\n' "work-list" \
        "$(json_len "${source}/data/${source}/${base}_filtered.json")" \
        "$DIM" "$(detail "${base}_filtered.json" "$files")" "$RESET"

    if [[ "$full" == "full" ]]; then
        printf '  %-14s %s articles   %s%s%s\n' "raw scrape" \
            "$(json_len "${source}/data/${source}/${base}.json")" \
            "$DIM" "$(detail "${base}.json" "$files")" "$RESET"
        printf '  %-14s %s articles   %s%s%s\n' "yesterday" \
            "$(json_len "${source}/data/${source}/${base}_yesterday.json")" \
            "$DIM" "$(detail "${base}_yesterday.json" "$files")" "$RESET"
        printf '  %-14s %s%s%s\n' "pruned rows" \
            "$DIM" "$(detail "$pruned" "$files")" "$RESET"
        printf '  %-14s %s\n' "objects" "$(printf '%s\n' "$files" | grep -c 'gs://')"
    fi

    # Archived runs. `ls` on the archive prefix lists one line per run folder.
    local runs latest
    runs="$(gcloud storage ls "gs://${BUCKET}/${source}/archive/" --project "$PROJECT" 2>/dev/null)"

    if [[ -n "$runs" ]]; then
        latest="$(printf '%s\n' "$runs" | tail -n1 | sed 's|.*/archive/||; s|/$||')"
        printf '  %-14s %s   %slatest %s%s\n' "runs archived" \
            "$(printf '%s\n' "$runs" | grep -c 'archive/')" "$DIM" "$latest" "$RESET"
    else
        printf '  %-14s %s0%s\n' "runs archived" "$DIM" "$RESET"
    fi

    echo
}

list_runs() {
    local source="$1"
    echo "${BOLD}${source^^} archived runs${RESET}  ${DIM}(newest last, 60-day retention)${RESET}"
    gcloud storage ls "gs://${BUCKET}/${source}/archive/" --project "$PROJECT" 2>/dev/null \
        | sed 's|.*/archive/||; s|/$||' \
        | sed 's/^/  /' \
        || echo "  none"
}

get_file() {
    local source="$1" file="$2" run="${3:-}"

    if [[ -n "$run" ]]; then
        gcloud storage cat "gs://${BUCKET}/${source}/archive/${run}/${file}" --project "$PROJECT"
    else
        gcloud storage cat "gs://${BUCKET}/${source}/data/${file}" --project "$PROJECT"
    fi
}

# ── arguments ───────────────────────────────────────────────────────────
[[ "${1:-}" == "-h" || "${1:-}" == "--help" ]] && usage 0

SOURCE="${1:-}"

if [[ -z "$SOURCE" ]]; then
    require_bucket
    summary idx brief
    summary sgx brief
    echo "${DIM}Full detail: $(basename "$0") idx${RESET}"
    exit 0
fi

if [[ "$SOURCE" != "idx" && "$SOURCE" != "sgx" ]]; then
    echo "Unknown pipeline '${SOURCE}' — expected 'idx' or 'sgx'." >&2
    usage 1
fi

require_bucket
ACTION="${2:-summary}"

case "$ACTION" in
    summary)
        summary "$SOURCE" full
        ;;
    runs)
        list_runs "$SOURCE"
        ;;
    get)
        FILE="${3:-}"
        [[ -n "$FILE" ]] || { echo "get needs a file, e.g. last_state.json" >&2; exit 1; }
        RUN=""
        [[ "${4:-}" == "--run" ]] && RUN="${5:-}"
        get_file "$SOURCE" "$FILE" "$RUN"
        ;;
    *)
        echo "Unknown action '${ACTION}'." >&2
        usage 1
        ;;
esac
