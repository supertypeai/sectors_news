#!/bin/bash
# One-time project setup, shared by both pipelines. Idempotent — safe to re-run.
#
#   ./bootstrap.sh                 # APIs, registry, bucket, service account, IAM
#   ./bootstrap.sh --seed          # ... and seed the state prefixes from data/
#
# Secrets are NOT managed here. The runtime values go in as plain environment
# variables at deploy time, read from .env at the repo root — see write_env_file
# in config.sh and the note in each deploy.sh. Rotating a value therefore means
# editing .env and re-running deploy.sh, not re-running this.
#
set -e

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "${HERE}/../.." && pwd)"
source "${HERE}/config.sh"

echo "== APIs =="
# storage, run, cloudbuild, scheduler and artifactregistry were already enabled
# on this project; iam was not. secretmanager is deliberately absent — nothing
# here uses it.
gcloud services enable \
    run.googleapis.com \
    cloudbuild.googleapis.com \
    cloudscheduler.googleapis.com \
    artifactregistry.googleapis.com \
    iam.googleapis.com \
    storage.googleapis.com \
    --project "$PROJECT"

echo "== Artifact Registry =="
# cloud-run-source-deploy already exists in us-central1, so this is normally a
# no-op — it is here so the script still works if the repo is ever deleted or
# the region in config.sh changes.
gcloud artifacts repositories describe "$REPO" \
    --location "$REGION" --project "$PROJECT" >/dev/null 2>&1 \
    || gcloud artifacts repositories create "$REPO" \
        --repository-format=docker \
        --location "$REGION" \
        --project "$PROJECT" \
        --description "Cloud Run job images"

echo "== State bucket =="
gcloud storage buckets describe "gs://${BUCKET}" --project "$PROJECT" >/dev/null 2>&1 \
    || gcloud storage buckets create "gs://${BUCKET}" \
        --project "$PROJECT" \
        --location "$REGION" \
        --uniform-bucket-level-access

# actions/upload-artifact had retention-days: 60. This is that setting. It is
# scoped to archive/ by prefix so it can never touch the live state tree under
# idx/data/ or sgx/data/ — deleting last_state.json would silently reset the
# incremental watermark.
LIFECYCLE="$(mktemp)"
cat >"$LIFECYCLE" <<'JSON'
{
  "lifecycle": {
    "rule": [
      {
        "action": {"type": "Delete"},
        "condition": {
          "age": 60,
          "matchesPrefix": ["idx/archive/", "sgx/archive/"]
        }
      }
    ]
  }
}
JSON
gcloud storage buckets update "gs://${BUCKET}" --project "$PROJECT" --lifecycle-file="$LIFECYCLE"
rm -f "$LIFECYCLE"

echo "== Service account =="
gcloud iam service-accounts describe "$SA" --project "$PROJECT" >/dev/null 2>&1 \
    || gcloud iam service-accounts create "$SA_NAME" \
        --project "$PROJECT" \
        --display-name "Sectors news scraping pipelines"

# objectAdmin, not objectCreator: the job overwrites last_state.json and the
# work-list every run, and overwriting an object needs delete.
gcloud storage buckets add-iam-policy-binding "gs://${BUCKET}" \
    --project "$PROJECT" \
    --member "serviceAccount:${SA}" \
    --role roles/storage.objectAdmin >/dev/null

# roles/run.invoker is deliberately NOT granted. Cloud Scheduler triggers the
# jobs as SCHEDULER_SA (the default compute account), which already holds
# roles/editor — and roles/editor includes run.jobs.run. Nothing to grant.
#
# roles/secretmanager.secretAccessor is not granted either, and no secrets are
# created: nothing here uses Secret Manager. roles/editor can neither set a
# project IAM policy nor access a secret payload, so the runtime values are
# passed as environment variables instead. See deployments/README.md for what
# that trades away and how to switch back.

if [[ " $* " == *" --seed "* ]]; then
    echo "== Seeding state prefixes from ${ROOT}/data =="
    # First run only. Without this the jobs still work — the image carries a copy
    # of data/ and State.pull leaves it alone when the bucket is empty — but the
    # 8.7 MB history in outdated_news.json would restart from the image's copy
    # every time the image is rebuilt. Seeding makes the bucket authoritative
    # from the start.
    for PREFIX in idx sgx; do
        gcloud storage rsync --recursive "${ROOT}/data" "gs://${BUCKET}/${PREFIX}/data" --project "$PROJECT"
    done
fi

echo
echo "Done. Next:"
echo "  deployments/pipeline_idx/deploy.sh && deployments/pipeline_idx/schedule.sh"
echo "  deployments/pipeline_sgx/deploy.sh && deployments/pipeline_sgx/schedule.sh"
