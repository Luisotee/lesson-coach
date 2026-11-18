#!/usr/bin/env bash
# Creates (or confirms) everything in rg-akelius-coach. Safe to re-run: each step
# checks whether the resource exists first. Writes endpoint, key and deployment
# names into the local .env (gitignored). Never prints the key.
set -euo pipefail
source "$(dirname "$0")/config.sh"
azure_names

log() { printf '==> %s\n' "$*"; }

for ns in Microsoft.CognitiveServices Microsoft.App Microsoft.ContainerRegistry; do
  state="$(az provider show -n "$ns" --query registrationState -o tsv)"
  if [[ "$state" != "Registered" ]]; then
    log "registering provider $ns (subscription-wide, needed once)"
    az provider register -n "$ns" --wait
  fi
done
if ! az extension show --name containerapp -o none 2>/dev/null; then
  log "installing the az containerapp extension"
  az extension add --name containerapp --only-show-errors
fi

log "resource group $RG"
if [[ "$(az group exists -n "$RG")" != "true" ]]; then
  az group create -n "$RG" -l "$LOCATION" -o none
fi

log "AI Services account $AI_ACCOUNT"
if ! az cognitiveservices account show -g "$RG" -n "$AI_ACCOUNT" -o none 2>/dev/null; then
  # A manual or interrupted delete leaves the account soft-deleted (down.sh purges it);
  # recover it, with its old keys, instead of failing on the taken name.
  if az cognitiveservices account list-deleted --query "[?name=='$AI_ACCOUNT'] | [0].name" -o tsv | grep -q .; then
    az cognitiveservices account recover -g "$RG" -n "$AI_ACCOUNT" -l "$LOCATION" -o none
  else
    az cognitiveservices account create -g "$RG" -n "$AI_ACCOUNT" -l "$LOCATION" \
      --kind AIServices --sku S0 --custom-domain "$AI_ACCOUNT" --yes -o none
  fi
fi

deploy() { # name model version sku capacity
  local name="$1" model="$2" version="$3" sku="$4" capacity="$5"
  log "deployment $name ($model $version, $sku, ${capacity}k TPM)"
  local actual
  if actual="$(az cognitiveservices account deployment show -g "$RG" -n "$AI_ACCOUNT" \
    --deployment-name "$name" \
    --query '[properties.model.name, properties.model.version, sku.name, to_string(sku.capacity)]' \
    -o tsv 2>/dev/null)"; then
    # It exists: fail rather than log a SKU it doesn't have (live must stay DataZoneStandard).
    read -r a_model a_version a_sku a_capacity <<<"$(tr '\n\t' '  ' <<<"$actual")"
    if [[ "$a_model $a_version $a_sku" != "$model $version $sku" ]]; then
      echo "ERROR: deployment $name is $a_model $a_version $a_sku, config says $model $version $sku." >&2
      echo "Delete it or rename the deployment in infra/config.sh, then re-run." >&2
      exit 1
    fi
    if [[ "$a_capacity" != "$capacity" ]]; then
      echo "WARNING: deployment $name has ${a_capacity}k TPM, config says ${capacity}k; left as is." >&2
    fi
    return
  fi
  az cognitiveservices account deployment create -g "$RG" -n "$AI_ACCOUNT" \
    --deployment-name "$name" --model-format OpenAI --model-name "$model" \
    --model-version "$version" --sku-name "$sku" --sku-capacity "$capacity" -o none
}
deploy "$LIVE_DEPLOYMENT" "$LIVE_MODEL" "$LIVE_VERSION" "$LIVE_SKU" "$LIVE_CAPACITY"
deploy "$OFFLINE_DEPLOYMENT" "$OFFLINE_MODEL" "$OFFLINE_VERSION" "$OFFLINE_SKU" "$OFFLINE_CAPACITY"

log "container registry $ACR_NAME (Basic)"
if ! az acr show -g "$RG" -n "$ACR_NAME" -o none 2>/dev/null; then
  az acr create -g "$RG" -n "$ACR_NAME" -l "$LOCATION" --sku Basic --admin-enabled false -o none
fi

log "Container Apps environment $CAE_NAME (consumption)"
# Existence via `az resource list`, assigned on its own line so an auth or network error
# stops the script (set -e) instead of looking like "not found" and creating a second
# environment. Inside [[ -n "$(...)" ]] a failure would not trip set -e.
found="$(az resource list -g "$RG" --resource-type Microsoft.App/managedEnvironments \
  --query "[?name=='$CAE_NAME'].name" -o tsv)"
if [[ -n "$found" ]]; then
  mode="$(az containerapp env show -g "$RG" -n "$CAE_NAME" --query properties.environmentMode -o tsv)"
  # Newer CLIs default to the Express mode, which can't pull from ACR with the app's
  # managed identity. deploy.sh needs WorkloadProfiles (with the Consumption profile).
  if [[ "$mode" != "WorkloadProfiles" ]]; then
    echo "ERROR: $CAE_NAME is in $mode mode; deploy.sh needs WorkloadProfiles." >&2
    echo "Delete it (and its apps) with: az containerapp env delete -g $RG -n $CAE_NAME, then re-run." >&2
    exit 1
  fi
else
  # No Log Analytics workspace: nothing is stored, and console logs still stream
  # with `az containerapp logs show`.
  az containerapp env create -g "$RG" -n "$CAE_NAME" -l "$LOCATION" \
    --environment-mode WorkloadProfiles --logs-destination none -o none
fi

log "writing $ENV_FILE"
endpoint="$(az cognitiveservices account show -g "$RG" -n "$AI_ACCOUNT" \
  --query 'properties.endpoints."OpenAI Language Model Instance API"' -o tsv)"
key="$(az cognitiveservices account keys list -g "$RG" -n "$AI_ACCOUNT" --query key1 -o tsv)"
if [[ -z "$endpoint" || -z "$key" ]]; then
  echo "ERROR: empty endpoint or key for $AI_ACCOUNT (still provisioning?); .env not changed. Re-run later." >&2
  exit 1
fi

set_env() { # KEY VALUE: replace the line if present, else append
  local k="$1" v="$2" tmp
  tmp="$(mktemp)"
  grep -v "^$k=" "$ENV_FILE" >"$tmp" || true
  printf '%s=%s\n' "$k" "$v" >>"$tmp"
  cat "$tmp" >"$ENV_FILE"
  rm -f "$tmp"
}
umask 077
touch "$ENV_FILE"
chmod 600 "$ENV_FILE"
set_env AZURE_OPENAI_ENDPOINT "$endpoint"
set_env AZURE_OPENAI_API_KEY "$key"
set_env AZURE_OPENAI_API_VERSION "$API_VERSION"
set_env MODEL_LIVE "$LIVE_DEPLOYMENT"
set_env MODEL_OFFLINE "$OFFLINE_DEPLOYMENT"

log "deployments (verified with the CLI)"
az cognitiveservices account deployment list -g "$RG" -n "$AI_ACCOUNT" \
  --query '[].{Name:name, Model:properties.model.name, Version:properties.model.version, Sku:sku.name, Capacity:sku.capacity}' \
  -o table

log "done: endpoint $endpoint, deployments $LIVE_DEPLOYMENT and $OFFLINE_DEPLOYMENT, key in $ENV_FILE"
