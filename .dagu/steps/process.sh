#!/usr/bin/env bash
set -euo pipefail

total=$(python - "$WORK_LIST" <<'PY'
import json, sys
try:
    print(len(json.load(open(sys.argv[1]))))
except (FileNotFoundError, json.JSONDecodeError, TypeError):
    print(0)
PY
)

batches=$(( (total + BATCH_SIZE - 1) / BATCH_SIZE ))
echo "$total article(s) -> $batches batch(es)"

for batch in $(seq 1 "$batches"); do
    echo "=== B${batch} ==="
    python -m scraper_engine.pipeline "$PIPELINE_COMMAND" \
        --process-only --batch "$batch" --batch-size "$BATCH_SIZE"
    sleep "$BATCH_PAUSE_SECONDS"
done

echo "=== CLEANUP ==="
python -m scraper_engine.pipeline remove_outdated_news --table-name "$TABLE_NAME" $CLEANUP_ARGS
