# Shared settings for up.sh, smoke.sh and down.sh. Sourced, not run.
# Every name here lives in RG; the scripts never touch any other resource group.

RG="rg-akelius-coach"
LOCATION="switzerlandnorth"

# Globally unique names get a short, stable suffix derived from the subscription id,
# so re-running the scripts always targets the same resources.
SUB_ID="$(az account show --query id -o tsv)"
SUFFIX="$(printf '%s' "$SUB_ID" | sha256sum | cut -c1-6)"

AI_ACCOUNT="ai-akelius-coach-$SUFFIX"
ACR_NAME="acrakeliuscoach$SUFFIX"
CAE_NAME="cae-akelius-coach"

# Live: EU data zone (per-teacher input). gpt-5.4-mini DataZoneStandard has 0 quota on
# Azure for Students, so live uses gpt-5.5 on DataZoneStandard (see docs/REASONING.md).
# Offline: no personal data, so GlobalStandard is fine (GlobalBatch can't be called interactively).
# Capacity is in thousands of tokens per minute.
LIVE_DEPLOYMENT="${LIVE_DEPLOYMENT:-gpt-5.5-live}"
LIVE_MODEL="${LIVE_MODEL:-gpt-5.5}"
LIVE_VERSION="${LIVE_VERSION:-2026-04-24}"
LIVE_SKU="${LIVE_SKU:-DataZoneStandard}"
LIVE_CAPACITY="${LIVE_CAPACITY:-100}"

OFFLINE_DEPLOYMENT="${OFFLINE_DEPLOYMENT:-gpt-5.5-offline}"
OFFLINE_MODEL="${OFFLINE_MODEL:-gpt-5.5}"
OFFLINE_VERSION="${OFFLINE_VERSION:-2026-04-24}"
OFFLINE_SKU="${OFFLINE_SKU:-GlobalStandard}"
OFFLINE_CAPACITY="${OFFLINE_CAPACITY:-250}"

API_VERSION="${API_VERSION:-2025-04-01-preview}"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${ENV_FILE:-$REPO_ROOT/.env}"
