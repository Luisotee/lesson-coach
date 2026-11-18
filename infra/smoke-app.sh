#!/usr/bin/env bash
# Smoke-tests the deployed app: health, topics, a sympy-only check, one mistake call that
# must reach the AI (a clean abstain is fine, "ai_unavailable" is not), and an SPA route.
#
#   infra/smoke-app.sh                 # the Container App's URL, looked up with az
#   infra/smoke-app.sh https://host    # any base URL (also a local server)
set -euo pipefail
source "$(dirname "$0")/config.sh"

if [[ $# -ge 1 ]]; then
  BASE="${1%/}"
else
  BASE="https://$(az containerapp show -g "$RG" -n "$APP_NAME" --query properties.configuration.ingress.fqdn -o tsv)"
fi
echo "smoke-testing $BASE"

fail=0
body="$(mktemp)"
trap 'rm -f "$body"' EXIT

# req METHOD PATH [JSON]: prints "HTTP <code> <seconds>s" and leaves the body in $body.
req() {
  local args=(-sS --retry 3 --retry-all-errors --max-time 90 -o "$body" -w '%{http_code} %{time_total}\n' -X "$1")
  [[ $# -ge 3 ]] && args+=(-H 'Content-Type: application/json' --data "$3")
  read -r code secs < <(curl "${args[@]}" "$BASE$2")
  printf '   HTTP %s in %.2fs\n' "$code" "$secs"
}
check() { # description jq-filter
  if [[ "$code" == 200 ]] && jq -e "$2" "$body" >/dev/null 2>&1; then
    echo "   ok: $1"
  else
    echo "   FAIL: $1"
    head -c 400 "$body"
    echo
    fail=1
  fi
}

echo "--> GET /api/health (cold start if the app was scaled to zero)"
req GET /api/health
check 'status ok' '.status == "ok"'

echo "--> GET /api/topics"
req GET /api/topics
check 'a list of topics' 'type == "array"'
echo "   topics: $(jq -r '[.[].id] | join(", ")' "$body" 2>/dev/null)"

echo "--> POST /api/check-working (sympy only)"
req POST /api/check-working '{"problem":{"text":"2*x + 6 = 10"},
  "lines":[{"left":"2*x + 6","right":"10","op":"-6"},{"left":"2*x","right":"4","op":"/2"},{"left":"x","right":"2"}]}'
check 'all lines follow' '.status == "all_follow"'

echo "--> POST /api/mistake (reaches the AI)"
req POST /api/mistake '{"problem":{"text":"3*x + 5 = 20"},"answer":{"text":"x = 7"},"lang":"en"}'
echo "   status: $(jq -r '"\(.status) \(.reason // "")"' "$body" 2>/dev/null), source: $(jq -r '.diagnosis.source // "none"' "$body" 2>/dev/null)"
check 'an AI reply or a clean abstain (not ai_unavailable)' \
  '(.status | IN("diagnosed","slip","unclear","out_of_scope")) and .reason != "ai_unavailable"'

echo "--> GET /mistake (SPA route)"
req GET /mistake
if [[ "$code" == 200 ]] && grep -qi '<div id="root"' "$body"; then echo "   ok: index.html"; else echo "   FAIL: not the SPA"; fail=1; fi

if [[ "$fail" != 0 ]]; then echo "APP SMOKE FAILED"; exit 1; fi
echo "APP SMOKE OK"
