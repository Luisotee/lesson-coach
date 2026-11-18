# Cost per teacher per month

**About $0.07 of AI per teacher per month with `gpt-5.5`, and about $0.01 with `gpt-5.4-mini`.** Hosting adds about $0.16–0.19 per teacher at 50–500 teachers, and under $0.02 at 20,000 or more. Content is generated once, so it costs nothing per teacher.

## What costs money, per request

Only two requests call a model live. Everything else (topic pages, practice, hints, checking typed working) is static JSON or sympy, with no model call.

| Live call | Tokens per call, measured (prompt / cached / output / reasoning) | `gpt-5.5` Data Zone | `gpt-5.4-mini` Data Zone |
|---|---|---|---|
| Mistake diagnosis (`/api/mistake`, only when no rule explains the answer) | 1516 / 1202 / 177 / 0 | **$0.0082** | $0.0012 |
| Reading a photo or drawing (`/api/transcribe`) | 482 / 0 / 39 / 0 | **$0.0039** | $0.0006 |

- **Tokens:** the means over 33 calls each in the final eval run (`reasoning_effort: none`, the default), from [`evals/results.yaml`](../evals/results.yaml). About 80% of the mistake prompt is cached, because its fixed instructions and topic context come first.
- **Prices**, USD per 1M tokens, Azure retail prices API ([prices.azure.com](https://prices.azure.com/api/retail/prices)), EU Data Zone meters, read 2026-11-18:

  | Model | Input | Cached input | Output |
  |---|---|---|---|
  | `gpt-5.5` (short context) | 5.50 | 0.55 | 33.00 |
  | `gpt-5.4-mini` | 0.825 | 0.0825 | 4.95 |

  Reasoning tokens bill as output; with `none` there are none.
- **`gpt-5.4-mini`** was the plan's live model. It has 0 Data Zone quota on this Azure for Students subscription, so live calls use `gpt-5.5`. Swapping back is config only: set `MODEL_LIVE` to a `gpt-5.4-mini` deployment. Its column assumes the same token counts; image tokens may differ by model, and its answer quality has not been evaluated.

## Per teacher per month

**The formula:** `(N × s × mistake call + M × image call) × (1 + retry rate)`, plus hosting ÷ teachers.

**The usage assumption**, stated plainly because nothing is measured yet: a teacher checks **N = 10** student answers a month and sends **M = 10** images (photos of student work, or drawn working in practice).
- **s**, the share of mistake checks that reach the model, is **37%** in the eval set (33 of 90 runs). The rest are settled by sympy alone: right answers, answers that are right but not simplified, and wrong answers a misconception rule reproduces. Real teachers' mix is unknown, so the worst case (every check reaches the model) is shown too.
- **The retry rate** is 3% (1 retry in 33 calls).

| | `gpt-5.5` | `gpt-5.4-mini` |
|---|---|---|
| AI, typical (s = 37%) | **$0.072** | $0.011 |
| AI, worst case (s = 100%) | $0.125 | $0.019 |

## Hosting

Prices for Switzerland North, from the Azure retail prices API, read 2026-11-18:
- **Container Apps (consumption):** $0.000024 per vCPU-second and $0.000003 per GiB-second while active. Our replica (1 vCPU, 2 GiB) costs **$0.108 an hour**, and nothing while scaled to zero. The monthly free grant (180,000 vCPU-s and 360,000 GiB-s) covers the first **50 hours**. Requests are free up to 2 million a month. A Consumption-only environment has no management fee.
- **Container registry, Basic:** $0.1666 a day, **$5.06 a month**. It is the only fixed cost.
- **No log workspace**, so nothing is ingested.

**Assumption:** each teacher has 4 sessions a month of 20 minutes, and the replica stays up about 7 minutes after the last request (measured: 6.75 minutes, see [`infra/README.md`](../infra/README.md)). Sessions are counted as if they never overlap, which is an upper bound.

| Teachers | Replica awake | Hosting a month | Hosting per teacher | **Total per teacher** (`gpt-5.5`) | Total (`gpt-5.4-mini`) |
|---|---|---|---|---|---|
| 50 | ~90 h (40 h billed) | $9.38 | $0.19 | **$0.26** | $0.20 |
| 500 | always on (730 h) | $78.50 | $0.16 | **$0.23** | $0.17 |
| 20,000 | ~4 replicas, always on | ~$320 | $0.016 | **$0.09** | $0.03 |
| 50,000 | ~10 replicas, always on | ~$790 | $0.016 | **$0.09** | $0.03 |

The 20,000 and 50,000 rows are rough: the replica count is a guess, not a load test. They also need a change first: today the app runs **at most one replica**, because the rate limit is held in memory. More replicas need a shared rate limit (for example Redis, or limits at a front door). At that scale, AI is most of the cost: about $1,400 a month for 20,000 teachers with `gpt-5.5`.

## One-off costs (offline)

| Item | Cost | Source |
|---|---|---|
| English packs: generation and verification (3 topics; 18 generation and 22 judge calls) | $1.06 | [`evals/verify-report.md`](../evals/verify-report.md) |
| Translation into 17 more languages (packs and UI strings, with judge and repairs) | $52.60 | [`evals/translation-report.md`](../evals/translation-report.md) |
| Evals (210 live calls and 144 judge calls) | $2.17 | [`evals/README.md`](../evals/README.md) |

That's about $56 in all, spent once. Spread over 20,000 teachers it is $0.003 per teacher. A new language costs about $1.20 for packs and $0.55 for UI strings, once the pipeline has settled (the first French run cost $5.39 before the judge was fixed). A new topic costs about $0.35 in English.

## How to lower it

1. **Switch the live model to `gpt-5.4-mini`** once there is Data Zone quota: AI cost falls about 7× (config only, `MODEL_LIVE`; re-run the evals first).
2. **Add misconception rules.** Every wrong answer a rule reproduces is answered with no model call, and with more certainty. Rules already settle 39 of the 72 wrong-answer runs in the evals.
3. **Keep prompts cache-friendly:** fixed instructions and topic context first, the teacher's input last. About 80% of mistake prompt tokens are already cached at a tenth of the price.
4. **Run offline work through the Batch API** (GlobalBatch, half price) once the pipeline no longer needs interactive retries.
5. **Hosting:** keep scale to zero. The $5 registry could move to a free registry. At scale, move the rate limit to a shared store so that replicas can scale with load.
6. **Keep `reasoning_effort: none`**: the evals found `low` no more accurate for these tasks, and reasoning tokens bill as output.
