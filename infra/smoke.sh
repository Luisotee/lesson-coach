#!/usr/bin/env bash
# Gets a structured-output (JSON schema) reply from both deployments, plus an image
# reading from the live one (transcription needs vision). Reads .env; never prints the key.
set -euo pipefail
source "$(dirname "$0")/config.sh"

set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a
: "${AZURE_OPENAI_ENDPOINT:?missing in .env; run infra/up.sh}"
: "${AZURE_OPENAI_API_KEY:?missing in .env; run infra/up.sh}"

call() { # deployment request-json -> response content (a JSON string)
  local url="${AZURE_OPENAI_ENDPOINT%/}/openai/deployments/$1/chat/completions?api-version=$AZURE_OPENAI_API_VERSION"
  local body status
  body="$(mktemp)"
  status="$(curl -sS --retry 3 --retry-all-errors -o "$body" -w '%{http_code}' -X POST "$url" \
    -H "api-key: $AZURE_OPENAI_API_KEY" -H 'Content-Type: application/json' --data @-)"
  if [[ "$status" != 200 ]]; then
    echo "FAIL $1: HTTP $status" >&2
    jq -c '.error // .' "$body" >&2
    rm -f "$body"
    return 1
  fi
  jq -r '"   tokens: \(.usage.prompt_tokens) in, \(.usage.completion_tokens) out", "   model: \(.model)"' "$body" >&2
  jq -r '.choices[0].message.content' "$body"
  rm -f "$body"
}

solve_schema='{
  "name": "solution", "strict": true,
  "schema": {"type": "object", "additionalProperties": false,
    "required": ["x", "explanation"],
    "properties": {"x": {"type": "number"}, "explanation": {"type": "string"}}}}'

lines_schema='{
  "name": "transcription", "strict": true,
  "schema": {"type": "object", "additionalProperties": false, "required": ["lines"],
    "properties": {"lines": {"type": "array", "items": {
      "type": "object", "additionalProperties": false,
      "required": ["left", "right", "confidence"],
      "properties": {"left": {"type": "string"}, "right": {"type": "string"},
        "confidence": {"type": "number"}}}}}}}'

fail=0
for dep in "$MODEL_LIVE" "$MODEL_OFFLINE"; do
  echo "--> $dep: structured output"
  out="$(jq -n --argjson s "$solve_schema" '{
      messages: [{role: "user", content: "Solve 3x + 5 = 20 for x. One-sentence explanation."}],
      response_format: {type: "json_schema", json_schema: $s},
      max_completion_tokens: 2000, reasoning_effort: "low"}' | call "$dep")" || { fail=1; continue; }
  echo "   $out"
  if [[ "$(jq -r '.x' <<<"$out")" == 5 ]]; then echo "   ok"; else echo "   FAIL: x != 5"; fail=1; fi
done

echo "--> $MODEL_LIVE: image input (fixtures/equation.png)"
img="data:image/png;base64,$(base64 -w0 "$(dirname "$0")/fixtures/equation.png")"
if out="$(jq -n --arg img "$img" --argjson s "$lines_schema" '{
    messages: [{role: "user", content: [
      {type: "text", text: "Transcribe each line of math in this image as left and right sides of the equals sign, using sympy syntax (3*x)."},
      {type: "image_url", image_url: {url: $img}}]}],
    response_format: {type: "json_schema", json_schema: $s},
    max_completion_tokens: 2000, reasoning_effort: "low"}' | call "$MODEL_LIVE")"; then
  echo "   $out"
  if [[ "$(jq '.lines | length' <<<"$out")" == 2 ]]; then echo "   ok"; else echo "   FAIL: expected 2 lines"; fail=1; fi
else
  fail=1
fi

if [[ "$fail" != 0 ]]; then echo "SMOKE FAILED"; exit 1; fi
echo "SMOKE OK"
