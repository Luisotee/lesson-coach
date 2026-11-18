# infra

Idempotent az CLI scripts for the `rg-akelius-coach` resource group in `switzerlandnorth`. They create and change nothing outside that group (the first run registers three resource providers on the subscription, which is required once).

```bash
infra/up.sh         # create or confirm everything, then write endpoint, key and deployment names to .env
infra/smoke.sh      # structured-output reply from both deployments + an image reading on the live one
infra/deploy.sh     # build origin/main (or any ref) locally, push to ACR, deploy the Container App
infra/smoke-app.sh  # health, topics, check-working, one AI mistake call and an SPA route on the live URL
infra/down.sh       # delete rg-akelius-coach only, after you type its name; purges the soft-deleted AI account
```

**Live URL:** https://ca-lesson-coach.ashycliff-c7de378e.switzerlandnorth.azurecontainerapps.io

## Deploy and redeploy

```bash
infra/deploy.sh               # fetch origin/main, build, push, deploy, wait until the new revision is healthy
infra/deploy.sh <git-ref>     # any commit, branch or tag
infra/smoke-app.sh            # then smoke-test the live URL
cd frontend && BASE_URL=https://<live-url> pnpm exec playwright test   # the e2e suite against it
```

- The image is built from `git archive <ref>`, so it holds exactly the committed tree: never `.env` or local changes. It is tagged with the commit (`lesson-coach:<sha12>`), and a tag already in ACR is reused.
- Builds run on **local Docker**: ACR Tasks (`az acr build`) return `TasksOperationsNotAllowed` on Azure for Students.
- The app pulls from ACR with its **system-assigned identity**, which `deploy.sh` grants AcrPull (the ACR admin user stays off). The first run creates the app with a placeholder image so the identity exists before our image is pulled.
- The whole app spec is one YAML written by `deploy.sh` and applied with `az containerapp update --yaml`, so a re-run converges on it. The Azure OpenAI key is a Container Apps secret (`azure-openai-key`), referenced by `AZURE_OPENAI_API_KEY`; the YAML lives in a private temp dir that is deleted on exit. Endpoint, API version and `MODEL_LIVE` are plain env vars; `TRUST_PROXY=true` comes from the Dockerfile.
- Ingress is external on port 8000, HTTPS only. Startup, readiness and liveness probes use `/api/health`.
- Rate limit: behind the ingress the app keys on the right-most `X-Forwarded-For` hop (`TRUST_PROXY=true`). Checked on the live URL on 2026-11-18. From one machine, `/api/transcribe` returned 429 after 10 requests a minute, even with a different forged `X-Forwarded-For` on every request. A temporary Container Apps job, a second client sending a request every 7 s at the same time, never got a 429. So clients get separate buckets, and a forged header doesn't give a new one.
- Scale: `minReplicas: 0`, `maxReplicas: 1`, HTTP rule at 20 concurrent requests. One replica at most, because the rate limit is held in memory: a second replica would give every client a second bucket. 1 vCPU and 2 GiB, for the two sympy worker processes.

`up.sh` is safe to re-run: each step checks whether the resource exists first. It never prints the key. Names, models and capacities live in `config.sh`; the deployment variables can be overridden from the environment (for example `LIVE_MODEL=gpt-5.4-mini LIVE_DEPLOYMENT=gpt-5.4-mini-live infra/up.sh` if quota is granted later).

Prerequisites: `az login`, `jq`, `curl`, and the `containerapp` az extension (`up.sh` installs it). If az was installed with `uv tool` and extension installs fail with "Pip failed", add pip to its venv: `uv pip install --python ~/.local/share/uv/tools/azure-cli/bin/python pip`.

## What is created

| Resource | Name | SKU / settings |
|---|---|---|
| Resource group | `rg-akelius-coach` | `switzerlandnorth` |
| AI Services account (Azure OpenAI) | `ai-akelius-coach-<suffix>` | S0, pay per token |
| Deployment, live | `gpt-5.5-live` | `gpt-5.5` 2026-04-24, **DataZoneStandard** (EU data zone), 100k TPM |
| Deployment, offline | `gpt-5.5-offline` | `gpt-5.5` 2026-04-24, GlobalStandard, 250k TPM |
| Container registry | `acrakeliuscoach<suffix>` | Basic, admin user off |
| Container Apps environment | `cae-akelius-coach` | WorkloadProfiles mode, Consumption profile, no Log Analytics workspace |
| Container App (`deploy.sh`) | `ca-lesson-coach` | 1 vCPU, 2 GiB, 0–1 replicas, system-assigned identity |

`<suffix>` is the first six hex characters of the SHA-256 of the subscription id, so the globally unique names are stable across runs.

The environment is created in **WorkloadProfiles** mode. Newer az CLIs default to an "Express" mode, whose apps can't pull from ACR with a managed identity (`ExpressRegistrySystemIdentityNotSupported`); `up.sh` stops with a clear error if it finds an environment in another mode.

## Why these models

- The plan's live model, `gpt-5.4-mini` on DataZoneStandard, is offered in the region but has **0 quota** on Azure for Students (also 0 in Sweden Central, Germany West Central and France Central). `gpt-5.5` on DataZoneStandard has quota (333k TPM), so live calls stay in the EU data zone. Swapping back is config only: the app reads the deployment name from `MODEL_LIVE`.
- Offline generation uses no personal data, so GlobalStandard is fine. GlobalBatch would be cheaper, but it only works through the Batch API, not interactive calls.

## Cost notes

- **Azure OpenAI:** no fixed cost; billed per input and output token at the `gpt-5.5` price. DataZoneStandard costs a little more per token than GlobalStandard. Reasoning tokens are billed as output tokens, so keep `reasoning_effort` low and set `max_completion_tokens`. Prices: https://azure.microsoft.com/pricing/details/cognitive-services/openai-service/
- **Container registry Basic:** a fixed daily charge (about USD 5 a month), the only always-on cost here.
- **Container Apps (consumption):** billed per vCPU-second and GiB-second while a replica runs, with a monthly free grant (180,000 vCPU-s and 360,000 GiB-s per subscription). At 1 vCPU and 2 GiB, the grant covers about 50 hours of running replicas a month. The replica stays up for about 5 minutes after the last request, then scales to zero, so idle costs nothing. The first request after idle waits for a cold start (measured: 20.4 s for `/api/health` from zero, then 0.65 s warm).
- **No Log Analytics:** nothing is ingested or stored. Console logs still stream with `az containerapp logs show`.
- `infra/down.sh` removes everything when the review is over, the Container App included.
