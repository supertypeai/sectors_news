#!/bin/bash
# Build the image and (re)deploy the IDX Cloud Run job.
# Safe to re-run; deploys a new revision each time.
#
# Run deployments/common/bootstrap.sh first — it creates the registry, the state
# bucket, the service account and the secrets this references.
set -e

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "${HERE}/../.." && pwd)"
source "${ROOT}/deployments/common/config.sh"

IMAGE="${REGION}-docker.pkg.dev/${PROJECT}/${REPO}/sectors-news-idx:latest"
JOB="sectors-news-idx-job"

# Submit from the repo root: the build context has to include src/, data/ and
# deployments/common/.
cd "$ROOT"

echo "Building and pushing image (context: $ROOT)..."
gcloud builds submit \
    --project "$PROJECT" \
    --config deployments/pipeline_idx/cloudbuild.yaml \
    --substitutions=_IMAGE="$IMAGE" \
    .

# --max-retries=0, and this is the one setting not to relax.
#
# A retry restarts the container from scratch, which means it re-scrapes. But
# the checkpoint pushed before processing has already advanced the watermark in
# last_state.json, so the re-scrape finds nothing new and overwrites
# pipeline_filtered.json with an empty work-list — destroying the very articles
# the retry was meant to rescue. Recovery is a PROCESS_ONLY=1 execution, not a
# retry; see the README.
#
# --task-timeout=6h matches the GitHub job ceiling this ran under, and it needs
# to. Measured over 30 successful Actions runs (job-level, queue excluded):
# median 37 min, mean 57 min, p90 153 min, max 190 min. A 3h timeout would have
# killed roughly 1 run in 30 — and killing a run mid-processing is expensive
# here, because the work-list has to be resumed by hand. A timeout is a ceiling,
# not a reservation: you are billed for actual runtime either way, so the only
# cost of 6h is that a genuinely hung run burns longer before it is cut off.
#
# --memory=4Gi --cpu=2 is a starting point, not a measurement. The only config
# this pipeline is known to run on is a GitHub public-repo runner: 4 vCPU /
# 16 GiB. This is already a 2x CPU and 4x memory cut from that. A sampled run
# spent 31 min scraping and 124 min processing 269 articles at 27 s each, and
# that time goes to waiting on page loads and LLM APIs rather than to CPU — the
# article loop is sequential and single-threaded. Chrome and Chromium are the
# real consumers, and remove_outdated_news json.loads an 8.7 MB file. Halving
# again to 1 vCPU / 2 GiB saves ~$21/month but is an 8x memory cut from the
# proven baseline; check the utilization metrics first, because an OOM is a
# SIGKILL mid-processing that needs a manual PROCESS_ONLY resume.
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
    "STATE_PREFIX=idx" \
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
