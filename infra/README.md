# infra

Idempotent az CLI scripts for the `rg-akelius-coach` resource group in `switzerlandnorth`. They create and change nothing outside that group (the first run registers three resource providers on the subscription, which is required once).

```bash
infra/up.sh      # create or confirm everything, then write endpoint, key and deployment names to .env
infra/smoke.sh   # structured-output reply from both deployments + an image reading on the live one
infra/down.sh    # delete rg-akelius-coach only, after you type its name; purges the soft-deleted AI account
```

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
| Container Apps environment | `cae-akelius-coach` | Consumption profile, no Log Analytics workspace |

`<suffix>` is the first six hex characters of the SHA-256 of the subscription id, so the globally unique names are stable across runs.

The app itself is deployed into the environment in T12, with min replicas 0 (scale to zero).

## Why these models

- The plan's live model, `gpt-5.4-mini` on DataZoneStandard, is offered in the region but has **0 quota** on Azure for Students (also 0 in Sweden Central, Germany West Central and France Central). `gpt-5.5` on DataZoneStandard has quota (333k TPM), so live calls stay in the EU data zone. Swapping back is config only: the app reads the deployment name from `MODEL_LIVE`.
- Offline generation uses no personal data, so GlobalStandard is fine. GlobalBatch would be cheaper, but it only works through the Batch API, not interactive calls.

## Cost notes

- **Azure OpenAI:** no fixed cost; billed per input and output token at the `gpt-5.5` price. DataZoneStandard costs a little more per token than GlobalStandard. Reasoning tokens are billed as output tokens, so keep `reasoning_effort` low and set `max_completion_tokens`. Prices: https://azure.microsoft.com/pricing/details/cognitive-services/openai-service/
- **Container registry Basic:** a fixed daily charge (about USD 5 a month), the only always-on cost here.
- **Container Apps (consumption):** billed per vCPU-second and GiB-second while a replica runs, with a monthly free grant. Scaled to zero, idle costs nothing; the first request after idle has a cold start of a few seconds.
- **No Log Analytics:** nothing is ingested or stored. Console logs still stream with `az containerapp logs show`.
- `infra/down.sh` removes everything when the review is over.
