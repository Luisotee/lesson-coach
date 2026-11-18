# evals

How well the live parts work: the mistake diagnosis (`POST /api/mistake`) and the
transcription of photos and drawings (`POST /api/transcribe`). The numbers below are from
`results.yaml` (2026-11-18, `gpt-5.5-live` on Data Zone Standard, the English packs from T5,
the mistake prompt that keeps nudges to a hint). `backend/tests/test_evals.py` fails when the
prompts, schemas, packs, config defaults, the code that decides the results (rules, mistake
pipeline, the two endpoints, the numbers guard, the scoring) or these inputs change after the
run. `.env` and Container Apps overrides of the config are not pinned: the evals run on the code
defaults.

## Results

| | `none` | `low` |
|---|---|---|
| Verdict right (sympy: correct / not simplified / wrong) | 90/90 | 90/90 |
| False "mistake" on the 5 controls (student right) | 0/15 | 0/15 |
| Status as expected (diagnosed, slip, unclear, out of scope…) | 88.9% | 95.6% |
| Misconception id right, all 21 named cases | 79.4% | 82.5% |
| … the 13 a rule answers (no LLM call) | 100% | 100% |
| … the 8 the LLM answers | 45.8% | 54.2% |
| Same outcome in all 3 runs | 29/30 cases | 27/30 cases |
| AI text held back as `ai_unverified_math` | 0/33 | 0/33 |
| LLM output that failed the schema | 0/33 | 0/33 |
| "AI only" id right (rules hidden; **not product accuracy**) | 97.4% | 89.7% |
| Transcription: lines right / images right | 45/45, 33/33 | 45/45, 33/33 |
| Mistake LLM call, latency p50 / p90 | 2.74 / 3.15 s | 2.83 / 3.25 s |
| Transcription call, latency p50 / p90 | 1.55 / 2.12 s | 1.71 / 2.32 s |
| Mistake call: prompt / cached / completion / reasoning tokens | 1516 / 931 / 174 / 0 | 1516 / 892 / 177 / 0 |
| Transcription call: prompt / completion / reasoning tokens | 482 / 39 / 0 | 482 / 45 / 4 |
| Cost per mistake LLM call / per transcription | $0.0095 / $0.0040 | $0.0098 / $0.0041 |

Counts are over 3 runs (15 lines and 11 images per run). A request answered by sympy alone (controls,
rule matches, out of scope) took 4 ms at p50 and needed no LLM call; 57 of 90 product runs
were answered that way.

**Recommendation: `reasoning_effort: none` for both live tasks** (now the default in
`backend/app/config.py`). The two efforts are within noise of each other on accuracy: the
differences come from one or two borderline negative-number cases that flip between runs
(`-5 + (-9)` → `4` came back `unclear` in all 3 `none` runs and diagnosed in all 3 `low` runs;
the "AI only" cases went the other way). `none` was steadier over runs, a little cheaper and
faster, and `low` spent no reasoning tokens on diagnoses anyway, so it bought nothing
measurable. The sample is small. `minimal`, which the plan named, doesn't exist on gpt-5.5:
the API answers `400 - Unsupported value: 'reasoning_effort' does not support 'minimal' with
this model. Supported values are: 'none', 'low', 'medium', 'high', and 'xhigh'.`

The whole run cost **$2.32**: $1.60 for 210 live calls, all of which succeeded (2 needed a
retry), and $0.72 for 144 judge calls on the offline deployment.

## Nudges no longer give the method away

The first run found that 11 of 20 hand-labelled nudges spelled out the method ("keep the
first fraction, change to multiplication, flip the divisor"). The mistake prompt now says a
nudge is a short hint or question that points at where to look without naming the rule or the
steps, and that only the "tell" may state the method. After the rerun, **3 of 20** nudges in a
new hand-labelled sample still give the method away (each says to rewrite fractions as
same-size pieces, or that the 3 multiplies every term). The judge, though uncalibrated, moved
the same way: it rated 13 of 144 nudges "to some extent" revealing, down from 57 of 144.
The samples are different outputs of the same 30 cases, so this is a before/after on the same
inputs, not on the same texts.

A side effect to watch: with `none`, the negative-number cases came back `unclear` a little
more often than in the first run (status as expected 88.9%, from 93.3%). That is an abstain,
not wrong math, and `low` moved the other way (95.6%, from 93.3%), so it looks like run-to-run
drift on borderline cases rather than an effect of the nudge wording.

## The LLM judge is not calibrated, so its scores are not quoted

The judge (`judge.py`, `gpt-5.5-offline`) scores the AI's shown text on four dimensions. It
was checked against 20 hand labels (`judge_labels.yaml`) before quoting. **The hand labels are
the AI author's (Claude, which wrote these evals), not a teacher's**; Luis or a teacher can
relabel them and rerun `summarize`. Each label and each judge score carries a hash of the text
it rates, so a label or score left over from an earlier run is skipped (and counted in
`results.yaml`) instead of being compared with new text.

| Dimension | Agreement | Weighted kappa | Quoted |
|---|---|---|---|
| located | 13/20 | 0.15 | no |
| actionable | 20/20 | undefined (every label "yes") | no |
| not revealing | 16/20 | -0.08 | no |
| non-judgmental | 20/20 | undefined (every label "yes") | no |

The judge is more lenient than the hand labels and never answered "no". It called most of the
`unclear` answers' explanations fully "located" where the hand labels said "to some extent",
and it rated all 3 nudges the hand labels found revealing as not revealing (while flagging
one the labels passed). On
"actionable" and "non-judgmental", every output got "yes" from both, so the sample can't show
whether the judge tells the levels apart. All 144 judge calls returned valid output.

What the hand labels themselves found in the 20 outputs: no blame or labels about the student
in any of them, and a concrete next step in all of them.

## Weak spots

- **The LLM names an "other" case's misconception about half the time.** The MaE rows
  labelled `other` (no card fits) are where most misses come from. The LLM picks the nearest
  card or says `unclear`: for `-5 + (-9)` → `4` it said `two_negatives_make_positive` or
  `unclear`, and for `12n + 150 = 330` with `12n = 150 - 330` it said `sign_not_changed`.
  Both readings are defensible, so part of this is the labels. The cases whose card has no
  rule (`two_negatives_make_positive`, `simplify_one_part`, `distribute_first_term_only`) were
  right in most runs.
- **One misconception the LLM can miss:** with the rules hidden, `(4+10)/2` → `9`
  (`cancel_across_addition`) came back `slip` or `unclear` in some `low` runs. In the product a
  rule catches it before the LLM.
- **The numbers guard never fired (0 of 144 AI replies).** Its blind spot is real, though. It
  checks values, so new math whose value was given passes: "2/3 becomes 4/6, so 4/6 + 1/6 =
  5/6" and "(4/3)*(2/5) rather than (3/4)*(5/2)" were shown in the first run. Both were right,
  but sympy didn't produce them.
- **Transcription scored 100%, so these images are too easy to tell versions apart.** They are
  drawn with a stroke font, not written by people. Treat 100% as an upper bound for real
  teachers' photos; the next step is a set of real handwriting photos (with consent).
- **The prompt cache hit about 60% of mistake prompt tokens**, not all of them. Azure caches
  the stable prefix (system prompt plus topic cards, about 1280 tokens) on a best effort basis.
  Transcription prompts (482 tokens) are under the 1024-token caching minimum.
- **Small sample:** 30 cases × 3 runs per effort. One case changing its answer moves a rate
  by about 3 points, and two runs of the same eval differed by that much.

## What is measured, and how

- **`mistakes.yaml`** has 30 cases:
  - 16 adapted from MaE (`nancyotero-projects/math-misconceptions`, MIT, attributed in the file
    and in `content/ATTRIBUTION.md`), with the numbers changed and sympy-checked;
  - 6 of our own for misconceptions the MaE rows miss;
  - 5 controls where the student is right or right but not simplified;
  - a slip, an answer no misconception explains, and an out-of-scope equation.

  `backend/tests/test_content.py` checks every row with sympy. It also checks that a label a
  rule covers is reproduced by exactly that rule.
- **`transcription/`** has 11 images and `truth.yaml`. `00` is `infra/fixtures/equation.png`.
  The rest are drawn by `make_images.py` (`uv run evals/transcription/make_images.py`):
  - OpenCV's Hershey script stroke font, with per-glyph jitter in size, slant, baseline and
    stroke width, on squared paper or a white canvas;
  - stacked fractions drawn as a numerator, a bar and a denominator, and margin ops `| -5`;
  - photo variants: rotated 8°, sideways (90°), and dim, skewed and blurred with noise and a
    paper tint, saved as JPEG;
  - one image with words and no math.

  No real photos and no people.
- **`run.py run`** sends each case and image through the real app, `create_app()` under
  FastAPI's `TestClient`: the process pool, the rules, the numbers guard and the Azure client
  with its retries. It does this 3 times per reasoning effort, and stops itself at $5.
  - A wrapper around the app's LLM records each call's tokens, latency, attempts, errors and
    raw reply.
  - Outputs go to `outputs/*.jsonl`. They hold only these synthetic cases.
- **"AI only"** (`ai_only_not_product_accuracy` in `results.yaml`) reruns the 13 cases a rule
  answers with the rule matches hidden. It patches `analyse_mistake` inside `run.py` only, so
  the LLM must name the misconception from the cards. This measures the LLM, not the product.
- **Transcription is scored per line** after our normalisation. Each side is parsed by our
  parser, which keeps the written form: `3x` = `3*x`, but `2/4` ≠ `1/2`. The margin op is
  parsed by `parse_op`. The image with no math must come back `unclear`, with no lines.
- **Cost** uses the Azure retail prices for gpt-5.5 short context, per 1M tokens: Data Zone
  $5.50 input, $0.55 cached input, $33 output; Global $5.00, $0.50, $30. Reasoning tokens are
  billed as output.
- **`results.yaml`** is pinned by `fingerprint.py`; `summarize` refuses outputs that don't
  cover every case and image equally often (a budget stop), and keeps the recorded
  recommendation unless `--recommend` is given.
- **`judge.py`** scores the shown AI text with the app's offline `judge` task. Kappa is
  linearly weighted Cohen's kappa over "no" < "to some extent" < "yes". A dimension is quoted
  only at kappa ≥ 0.6.

## Rerun

```sh
make evals    # run (about $1.60), judge (about $0.75), summarize; needs the repo's .env
```

Or one step at a time:

```sh
uv run --project backend python evals/run.py run [--efforts none,low --runs 3 --budget 5]
uv run --project backend python evals/run.py run --cases ctrl-1,10-no-math   # a quick look:
                         # writes *-subset.jsonl (gitignored), which summarize ignores
uv run --project backend python evals/run.py judge --sample 20   # a new sample to hand-label
uv run --project backend python evals/run.py judge
uv run --project backend python evals/run.py summarize --recommend "…"
```

A new run gives new outputs, so the hand labels must be redone for the new sample: each
label refers to an output id and the hash of its text, and stale ones are skipped.
