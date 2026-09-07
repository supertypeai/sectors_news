#!/usr/bin/env bash
set -euo pipefail

git rebase --abort 2>/dev/null || true

case "${1:-}" in
    checkpoint) message="checkpoint ingested articles"; git add -- $CHECKPOINT_FILES ;;
    publish)    message="update scraped news data";     git add -A ;;
    *) echo "usage: commit.sh checkpoint|publish" >&2; exit 2 ;;
esac

git diff --cached --quiet || git commit -m "chore($MARKET): $message"

if [ -z "$(git log --format=%H "origin/$GIT_BRANCH..HEAD")" ]; then
    echo "nothing to push"
    exit 0
fi

git pull --rebase origin "$GIT_BRANCH"
git push origin "HEAD:$GIT_BRANCH"
