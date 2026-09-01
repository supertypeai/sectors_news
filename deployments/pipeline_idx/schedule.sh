#!/bin/bash
# Creates (or updates) the Cloud Scheduler job that triggers the IDX Cloud Run
# job. Run once after deploy.sh.
set -e

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$(cd "${HERE}/../.." && pwd)/deployments/common/config.sh"

# Triggered as SCHEDULER_SA, not as the job's own runtime account: that
# identity needs permission to invoke, and roles/run.invoker cannot be
# granted with the permissions available here. The default compute account
# already has roles/editor, which includes run.jobs.run. See common/config.sh.
JOB="sectors-news-idx-job"
SCHEDULER_JOB="sectors-news-idx-4hourly"

# Unchanged from the workflow: `cron: "15 */4 * * *"`, i.e. 00:15, 04:15, 08:15,
# 12:15, 16:15 and 20:15 UTC. GitHub's schedule trigger is always UTC, so the
# time zone here is Etc/UTC and not Asia/Jakarta — pinning it to WIB would move
# every run by seven hours.
#
# The :15 offset is the whole of the staggering between the two pipelines. On
# GitHub they also shared `concurrency: news-data-pipeline` with `queue: max`,
# which serialised them; that group existed because both jobs pushed data/ to
# the same branch and a concurrent push would have conflicted. Cloud Run has no
# cross-job equivalent and does not need one: each job owns its own GCS prefix
# and its own Supabase table, so an overlap costs nothing but scraper egress.
SCHEDULE="15 */4 * * *"

URI="https://${REGION}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${PROJECT}/jobs/${JOB}:run"

gcloud scheduler jobs create http "$SCHEDULER_JOB" \
    --project "$PROJECT" \
    --location "$REGION" \
    --schedule "$SCHEDULE" \
    --uri "$URI" \
    --http-method POST \
    --oauth-service-account-email "$SCHEDULER_SA" \
    --time-zone "Etc/UTC" \
    --description "Trigger the IDX news scrape/process Cloud Run job every 4 hours" \
    || gcloud scheduler jobs update http "$SCHEDULER_JOB" \
        --project "$PROJECT" \
        --location "$REGION" \
        --schedule "$SCHEDULE" \
        --uri "$URI" \
        --http-method POST \
        --oauth-service-account-email "$SCHEDULER_SA" \
        --time-zone "Etc/UTC"

echo "Scheduler job '$SCHEDULER_JOB' set to '$SCHEDULE' (UTC)."
echo "Trigger manually with:"
echo "  gcloud scheduler jobs run $SCHEDULER_JOB --location=$REGION --project=$PROJECT"
