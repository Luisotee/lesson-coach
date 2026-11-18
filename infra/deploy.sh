#!/usr/bin/env bash
# Builds a git ref (default: origin/main) with local Docker, pushes it to ACR and deploys it to the Container App.
# Needs Docker. Safe to re-run: an image already pushed for that commit is reused, and the app is
# updated in place (one active revision). Needs infra/up.sh to have run, and .env for
# the Azure OpenAI endpoint and key, which go into a Container Apps secret only.
#
#   infra/deploy.sh                # fetch and deploy origin/main
#   infra/deploy.sh <git-ref>      # deploy any commit, branch or tag
set -euo pipefail
source "$(dirname "$0")/config.sh"
azure_names

log() { printf '==> %s\n' "$*"; }

REF="${1:-origin/main}"
[[ "$REF" == origin/* ]] && git -C "$REPO_ROOT" fetch -q origin "${REF#origin/}"
SHA="$(git -C "$REPO_ROOT" rev-parse --short=12 "$REF^{commit}")"
IMAGE="$ACR_NAME.azurecr.io/$IMAGE_REPO:$SHA"

[[ -f "$ENV_FILE" ]] || { echo "No $ENV_FILE; run infra/up.sh first." >&2; exit 1; }
set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a
for v in AZURE_OPENAI_ENDPOINT AZURE_OPENAI_API_KEY AZURE_OPENAI_API_VERSION MODEL_LIVE; do
  [[ -n "${!v:-}" ]] || { echo "$v is missing or empty in $ENV_FILE; run infra/up.sh." >&2; exit 1; }
done

for name in "$ACR_NAME" "$CAE_NAME"; do
  az resource list -g "$RG" --query "[?name=='$name'] | [0].name" -o tsv | grep -q . ||
    { echo "$name not found in $RG; run infra/up.sh first." >&2; exit 1; }
done

work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
chmod 700 "$work"

log "image $IMAGE ($REF)"
if az acr repository show -n "$ACR_NAME" --image "$IMAGE_REPO:$SHA" -o none 2>/dev/null; then
  echo "already built; reusing it"
else
  # Build exactly the committed tree, not the working copy (no .env, no local changes).
  mkdir "$work/ctx"
  git -C "$REPO_ROOT" archive "$SHA" | tar -x -C "$work/ctx"
  # ACR Tasks (`az acr build`) are not permitted on Azure for Students, so build locally.
  docker build --platform linux/amd64 -t "$IMAGE" "$work/ctx"
  az acr login -n "$ACR_NAME" --only-show-errors
  docker push "$IMAGE"
  rm -rf "$work/ctx"
fi

if ! az containerapp show -g "$RG" -n "$APP_NAME" -o none 2>/dev/null; then
  log "creating $APP_NAME (placeholder image until its identity can pull from ACR)"
  # The app pulls from ACR with its system-assigned identity (ACR admin user stays off).
  # The identity must exist and hold AcrPull before the first revision uses our image.
  az containerapp create -g "$RG" -n "$APP_NAME" --environment "$CAE_NAME" \
    --image mcr.microsoft.com/k8se/quickstart:latest --system-assigned \
    --ingress external --target-port 80 --min-replicas 0 --max-replicas 1 -o none
fi
principal="$(az containerapp show -g "$RG" -n "$APP_NAME" --query identity.principalId -o tsv)"
acr_id="$(az acr show -g "$RG" -n "$ACR_NAME" --query id -o tsv)"
if [[ -z "$(az role assignment list --assignee "$principal" --scope "$acr_id" --role AcrPull --query '[].id' -o tsv)" ]]; then
  # Granted explicitly: `az containerapp registry set --identity system` can leave it out.
  log "granting the app's identity AcrPull on $ACR_NAME"
  az role assignment create --assignee-object-id "$principal" --assignee-principal-type ServicePrincipal \
    --role AcrPull --scope "$acr_id" -o none
fi

log "deploying $APP_NAME"
# The whole spec in one file, so a re-run converges on it. It holds the key, so it lives
# in a private temp dir and is deleted on exit.
umask 077
cat >"$work/app.yaml" <<EOF
identity:
  type: SystemAssigned
properties:
  configuration:
    activeRevisionsMode: Single
    ingress:
      external: true
      targetPort: 8000
      transport: auto
      allowInsecure: false
    registries:
      - server: $ACR_NAME.azurecr.io
        identity: system
    secrets:
      - name: azure-openai-key
        value: "$AZURE_OPENAI_API_KEY"
  template:
    containers:
      - name: app
        image: $IMAGE
        resources:
          cpu: 1.0
          memory: 2Gi
        env:
          - name: AZURE_OPENAI_ENDPOINT
            value: "$AZURE_OPENAI_ENDPOINT"
          - name: AZURE_OPENAI_API_KEY
            secretRef: azure-openai-key
          - name: AZURE_OPENAI_API_VERSION
            value: "$AZURE_OPENAI_API_VERSION"
          - name: MODEL_LIVE
            value: "$MODEL_LIVE"
        probes:
          - type: Startup
            httpGet: {path: /api/health, port: 8000}
            periodSeconds: 2
            failureThreshold: 30
          - type: Readiness
            httpGet: {path: /api/health, port: 8000}
            periodSeconds: 10
          - type: Liveness
            httpGet: {path: /api/health, port: 8000}
            periodSeconds: 30
    scale:
      # Scale to zero when idle. One replica at most: the rate limit is in memory, so a
      # second replica would give every client a second bucket.
      minReplicas: 0
      maxReplicas: 1
      rules:
        - name: http
          http:
            metadata:
              concurrentRequests: "20"
EOF
for attempt in 1 2 3 4 5; do
  # Right after `registry set`, the AcrPull grant can take a minute to apply.
  if az containerapp update -g "$RG" -n "$APP_NAME" --yaml "$work/app.yaml" -o none; then
    break
  fi
  [[ "$attempt" == 5 ]] && { echo "deploy failed" >&2; exit 1; }
  echo "retrying in 30 s ($attempt/5)"
  sleep 30
done

fqdn="$(az containerapp show -g "$RG" -n "$APP_NAME" --query properties.configuration.ingress.fqdn -o tsv)"
log "waiting for the new revision to be ready, then https://$fqdn/api/health"
for _ in $(seq 1 60); do
  # Until the new revision is ready, the old one may still answer the health check.
  read -r latest ready < <(az containerapp show -g "$RG" -n "$APP_NAME" \
    --query '[properties.latestRevisionName, properties.latestReadyRevisionName]' -o tsv | paste -sd' ')
  if [[ "$latest" == "$ready" ]] && curl -fsS --max-time 20 "https://$fqdn/api/health" >/dev/null 2>&1; then
    log "live: https://$fqdn (image $SHA)"
    az containerapp revision list -g "$RG" -n "$APP_NAME" \
      --query '[?properties.active].{Revision:name, Image:properties.template.containers[0].image, Replicas:properties.replicas, Health:properties.healthState}' \
      -o table
    exit 0
  fi
  sleep 5
done
echo "the new revision was not ready and healthy within 5 minutes" >&2
exit 1
