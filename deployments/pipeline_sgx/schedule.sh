#!/bin/bash
# Creates (or updates) the Cloud Scheduler job that triggers the SGX Cloud Run
# job. Run once after deploy.sh.
set -e

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$(cd "${HERE}/../.." && pwd)/deployments/common/config.sh"

# Triggered as SCHEDULER_SA, not as the job's own runtime account: that
# identity needs permission to invoke, and roles/run.invoker cannot be
# granted with the permissions available here. The default compute account
# already has roles/editor, which includes run.jobs.run. See common/config.sh.
JOB="sectors-news-sgx-job"
SCHEDULER_JOB="sectors-news-sgx-4hourly"

# Unchanged from the workflow: `cron: "0 */4 * * *"`, i.e. on the hour at 00:00,
# 04:00, 08:00, 12:00, 16:00 and 20:00 UTC — fifteen minutes ahead of IDX.
# GitHub's schedule trigger is always UTC, so the time zone here is Etc/UTC and
# not Asia/Singapore; pinning it to SGT would move every run by eight hours.
#
# See pipeline_idx/schedule.sh for why the `concurrency: news-data-pipeline`
# group the two workflows shared has no counterpart here and does not need one.
SCHEDULE="0 */4 * * *"

URI="https://${REGION}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${PROJECT}/jobs/${JOB}:run"

gcloud scheduler jobs create http "$SCHEDULER_JOB" \
    --project "$PROJECT" \
    --location "$REGION" \
    --schedule "$SCHEDULE" \
    --uri "$URI" \
    --http-method POST \
    --oauth-service-account-email "$SCHEDULER_SA" \
    --time-zone "Etc/UTC" \
    --description "Trigger the SGX news scrape/process Cloud Run job every 4 hours" \
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
