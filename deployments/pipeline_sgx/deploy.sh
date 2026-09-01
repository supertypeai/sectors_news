#!/bin/bash
# Build the image and (re)deploy the SGX Cloud Run job.
# Safe to re-run; deploys a new revision each time.
#
# Run deployments/common/bootstrap.sh first — it creates the registry, the state
# bucket, the service account and the secrets this references.
set -e

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "${HERE}/../.." && pwd)"
source "${ROOT}/deployments/common/config.sh"

IMAGE="${REGION}-docker.pkg.dev/${PROJECT}/${REPO}/sectors-news-sgx:latest"
JOB="sectors-news-sgx-job"

# Submit from the repo root: the build context has to include src/, data/ and
# deployments/common/.
cd "$ROOT"

echo "Building and pushing image (context: $ROOT)..."
gcloud builds submit \
    --project "$PROJECT" \
    --config deployments/pipeline_sgx/cloudbuild.yaml \
    --substitutions=_IMAGE="$IMAGE" \
    .

# --max-retries=0, and this is the one setting not to relax.
#
# A retry restarts the container from scratch, which means it re-scrapes. But
# the checkpoint pushed before processing has already advanced the watermark in
# last_state_sgx.json, so the re-scrape finds nothing new and overwrites
# pipeline_sgx_filtered.json with an empty work-list — destroying the very
# articles the retry was meant to rescue. Recovery is a PROCESS_ONLY=1
# execution, not a retry; see the README.
#
# --task-timeout=6h matches the GitHub job ceiling this ran under. SGX is the
# small one — measured over 30 successful Actions runs (job-level, queue
# excluded): median 8.5 min, mean 8.4 min, p90 15 min, max 20 min — so the
# ceiling is pure headroom here rather than something the tail actually reaches.
# It is set the same as IDX deliberately: a timeout is a ceiling, not a
# reservation, and having the two jobs differ invites the wrong one being copied.
#
# --memory=4Gi --cpu=2 is a starting point, not a measurement, and is more
# obviously generous for SGX than for IDX — but it is deliberately the same as
# IDX so the two jobs stay one configuration rather than two. The proven
# baseline is a GitHub public-repo runner at 4 vCPU / 16 GiB; this is already a
# 2x CPU and 4x memory cut from it. Check the utilization metrics before going
# lower, because an OOM kills the task.
# The five runtime values are passed as plain environment variables rather
# than mounted from Secret Manager. Reading a secret needs
# roles/secretmanager.secretAccessor, which requires a project-level IAM
# binding that roles/editor cannot make — and roles/editor does not include
# secretmanager.versions.access either, so no existing account is a way round
# it. The trade: anyone with run.jobs.get on this project can read these
# values back out of `gcloud run jobs describe`. To switch to Secret Manager
# once an owner has granted the role, see deployments/README.md.
#
# The temp file is 0600 and removed on exit, including on failure.
ENV_VARS_FILE="$(mktemp)"
trap 'rm -f "$ENV_VARS_FILE"' EXIT

write_env_file "$ENV_VARS_FILE" \
    "STATE_BUCKET=${BUCKET}" \
    "STATE_PREFIX=sgx" \
    "BATCH_SIZE=30" \
    "BATCH_PAUSE_SECONDS=20" \
    || { echo "Refusing to deploy: the environment is incomplete." >&2; exit 1; }

echo "Deploying Cloud Run job..."
gcloud run jobs deploy "$JOB" \
    --project "$PROJECT" \
    --image "$IMAGE" \
    --region "$REGION" \
    --service-account "$SA" \
    --max-retries=0 \
    --task-timeout=6h \
    --memory=4Gi \
    --cpu=2 \
    --env-vars-file "$ENV_VARS_FILE"

echo "Done. Run manually with:"
echo "  gcloud run jobs execute $JOB --region=$REGION --project=$PROJECT"
echo
echo "Resume after a processing crash (the workflow_dispatch 'process_only' input):"
echo "  gcloud run jobs execute $JOB --region=$REGION --project=$PROJECT \\"
echo "      --update-env-vars PROCESS_ONLY=1"
