#!/usr/bin/env bash
set -euo pipefail

case "${1:-}" in
    checkpoint) message="checkpoint ingested articles"; git add -- $CHECKPOINT_FILES ;;
    # add -A, not a list: remove_outdated_news and the monthly companies.json
    # refresh write files nobody would think to name.
    publish)    message="update scraped news data";     git add -A ;;
    *) echo "usage: commit.sh checkpoint|publish" >&2; exit 2 ;;
esac

if git diff --cached --quiet; then
    echo "nothing to commit"
    exit 0
fi

git commit -m "chore($MARKET): $message"

for attempt in 1 2 3 4 5; do
    git pull --rebase origin "$GIT_BRANCH" && git push origin "HEAD:$GIT_BRANCH" && exit 0
    git rebase --abort 2>/dev/null || true
    sleep $(( attempt * 10 ))
    git fetch --prune origin
done

echo "could not push to $GIT_BRANCH after 5 attempts" >&2
exit 1
