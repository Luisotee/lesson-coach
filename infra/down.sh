#!/usr/bin/env bash
# Deletes rg-akelius-coach and nothing else, after a typed confirmation.
# Then purges the soft-deleted AI Services account so its name and quota free up.
set -euo pipefail
source "$(dirname "$0")/config.sh"
azure_names

if [[ "$(az group exists -n "$RG")" != "true" ]]; then
  echo "$RG does not exist; nothing to delete."
  exit 0
fi

echo "This permanently deletes resource group $RG and everything in it:"
az resource list -g "$RG" --query '[].{Name:name, Type:type}' -o table
read -r -p "Type the group name ($RG) to confirm: " answer
if [[ "$answer" != "$RG" ]]; then
  echo "Not confirmed; nothing deleted."
  exit 1
fi

az group delete -n "$RG" --yes
if az cognitiveservices account list-deleted --query "[?name=='$AI_ACCOUNT'] | [0].name" -o tsv | grep -q .; then
  az cognitiveservices account purge -g "$RG" -n "$AI_ACCOUNT" -l "$LOCATION"
fi
echo "Deleted $RG. The local .env still holds the old endpoint and key; they no longer work."
