# evals

How well the live parts work: the mistake diagnosis (`POST /api/mistake`) and the
transcription of photos and drawings (`POST /api/transcribe`). The numbers below are from
`results.yaml` (2026-11-18, `gpt-5.5-live` on Data Zone Standard, the English packs from T5,
the mistake prompt that keeps nudges to a hint, and the call that words a rule match's moves
for the student's problem, both asked to put math in backticks). `backend/tests/test_evals.py` fails when the
prompts, schemas, packs, config defaults, the code that decides the results (rules, mistake
pipeline and its math, the two endpoints, the numbers guard, the Azure client, the eval code)
or these inputs change after the run. `.env` overrides are not pinned; `results.yaml` records
the models and efforts that actually ran.

## Results

| | `none` | `low` |
|---|---|---|
| Verdict right (sympy: correct / not simplified / wrong) | 90/90 | 90/90 |
| False "mistake" on the 5 controls (student right) | 0/15 | 0/15 |
| Status as expected (diagnosed, slip, unclear, out of scope…) | 91.1% | 93.3% |
| Misconception id right, all 21 named cases | 81.0% | 81.0% |
| … the 13 a rule answers (no LLM diagnosis) | 100% | 100% |
| … the 8 the LLM answers | 50.0% | 50.0% |
| Rule matches whose moves were written for the student's problem | 39/39 | 39/39 |
| Shown AI texts with math outside backticks (drawn raw) | 1/72 | 1/72 |
| Same outcome in all 3 runs | 29/30 cases | 28/30 cases |
| AI text held back as `ai_unverified_math` | 0/33 | 0/33 |
| LLM output that failed the schema | 0/72 | 0/72 |
| "AI only" id right (rules hidden; **not product accuracy**) | 87.2% | 94.9% |
| Transcription: lines right / images right | 45/45, 33/33 | 45/45, 33/33 |
| Diagnosis call, latency p50 / p90 | 2.71 / 3.13 s | 2.72 / 3.07 s |
| Rule-match moves call, latency p50 / p90 | 1.83 / 2.40 s | 1.50 / 2.17 s |
| Transcription call, latency p50 / p90 | 1.46 / 2.00 s | 1.74 / 2.19 s |
| Diagnosis call: prompt / cached / completion / reasoning tokens | 1595 / 1086 / 186 / 0 | 1595 / 1047 / 187 / 0 |
| Moves call: prompt / cached / completion / reasoning tokens | 755 / 0 / 121 / 0 | 755 / 0 / 115 / 0 |
| Transcription call: prompt / completion / reasoning tokens | 482 / 39 / 0 | 482 / 47 / 7 |
| Cost per diagnosis / moves / transcription call | $0.0095 / $0.0082 / $0.0040 | $0.0097 / $0.0080 / $0.0042 |

**Math in backticks.** The page draws math in backticks by hand (the packs' convention) and
shows anything else as typed, so the live prompts now ask for every piece of math in
backticks. Before the change, 207 of 222 shown AI texts in the previous run had math outside
backticks (`3*x = 15` drawn with a raw `*`); in this run 3 of 222 are flagged (the row above
counts product runs; the third is an "AI only" run), and all 3 are slashes between words
("arithmetic/copying"), which the check's pattern also catches: no AI text shows raw math.
Of the 1641 spans in backticks, 1634 parse; the other 7 are shown as written: `| +120` (a
margin operation, 5 times) and `/2` (twice). Margin notes are asked for in words and drawn as
plain text, so any backtick in one is dropped; none had math. The status moved from 87.8% to
91.1% (`none`) and 92.2% to 93.3% (`low`) and the ids stayed at 81%, within the run-to-run
spread seen before, so the change did not cost accuracy.

Counts are over 3 runs (15 lines and 11 images per run). A request answered by sympy alone
(controls, out of scope) took 3 ms at p50 and needed no LLM call; 18 of 90 product runs were
answered that way. A rule match (39 runs) needs no LLM diagnosis, but one short call
(`mistake_moves`, 6 s deadline) words the card's moves for the student's problem; if it
failed, abstained, left a move blank or brought a number sympy didn't give it, the card's
own moves would be shown, framed by the card's example problem (or, on the card's own
problem, by its wrong answer). It never fell back in this run. Those moves are judged and
hand-labelled with the AI's diagnoses (below), and scored apart (`product_rule_moves` in
`results.yaml`). Latency and cache numbers move between runs of the same eval (the diagnosis
call's p50 was 2.5 to 3.1 s with `none` across five runs, the cache share 60% to 85%), so
compare the two columns, not runs.

**Recommendation: `reasoning_effort: none` for both live tasks** (the default in
`backend/app/config.py`), with a caveat. The two are close: `low` matched the expected
status in 2 more of 90 runs here, with the same misconception ids, and gave the same outcome
in all 3 runs for one case fewer; the costs are the same, and `low` spent no reasoning tokens
on diagnoses. Across the last five runs `low` was ahead on status by 1 to 4 of 90 runs each
time, so the lean toward `low` may be real; it is still within what one case flipping between
runs moves. Switching is config only (`MISTAKE_REASONING_EFFORT`), but it changes the pinned
results, so it needs its own eval run. `minimal`, which the plan named,
doesn't exist on gpt-5.5: the API answers `400 - Unsupported value: 'reasoning_effort' does
not support 'minimal' with this model. Supported values are: 'none', 'low', 'medium',
'high', and 'xhigh'.`

The whole run cost **$3.50**: $2.25 for 288 live calls, all of which succeeded (4 needed a
retry), and $1.24 for 222 judge calls on the offline deployment (144 diagnoses and 78
rule-match moves). `results.yaml` records the models and efforts that actually ran (from
`Settings`, so `.env` included).

## Nudges give the method away less often

The first run found that 11 of 20 hand-labelled nudges spelled out the method ("keep the
first fraction, change to multiplication, flip the divisor"). The mistake prompt now says a
nudge is a short hint or question that points at where to look without naming the rule or the
steps, and that only the "tell" may state the method. In the latest run, **4 of 20** nudges in
a new hand-labelled sample still give part of the method away. Two walk the number line
("start at 8 and move 3 steps left"), one states the method ("collect the `k` terms on one
side"), and one is a rule match's moves, whose nudge gives the step outright ("write
`| +120` in the margin and apply it to both sides", as the card's own nudge does). Earlier
runs with the same prompt had 3, 5, 6, 6 and 5 of 20. The judge, though uncalibrated, moved
the same way: it rated 12 of 144 diagnosis nudges and 20 of 78 rule-match nudges as at least
partly revealing, against 57 of 144 before the prompt change. The samples are different outputs of the same 30 cases, so
this is a before/after on the same inputs, not on the same texts.

## The LLM judge is not calibrated, so its scores are not quoted

The judge (`judge.py`, `gpt-5.5-offline`) scores the AI's shown text on four dimensions. It
was checked against 20 hand labels (`judge_labels.yaml`) before quoting. **The hand labels are
the AI author's (Claude, which wrote these evals), not a teacher's**; Luis or a teacher can
relabel them and rerun `summarize`. Each label and each judge score carries a hash of the text
it rates, so a label or score left over from an earlier run is skipped (and counted in
`results.yaml`) instead of being compared with new text.

| Dimension | Agreement | Weighted kappa | Quoted |
|---|---|---|---|
| located | 13/20 | 0.00 | no |
| actionable | 20/20 | undefined (every label "yes") | no |
| not revealing | 17/20 | 0.595 | no |
| non-judgmental | 20/20 | undefined (every label "yes") | no |

"Not revealing" came closest yet: kappa 0.595, just under the 0.6 bar, so it is still not
quoted. The judge missed 1 of the 4 nudges the hand labels found revealing, rated the
rule-match nudge that gives the step "to some extent" where the hand label says "no", and
flagged 1 nudge the hand labels passed. On "located" it called all 7 explanations the hand
labels found only partly located (mostly honest `unclear`s) fully located. Its agreement
moves from run to run (kappa 0.00 to 0.60 over the last four runs). On "actionable" and
"non-judgmental" every output got "yes" from both, so the sample can't show whether the
judge tells the levels apart. All 222 judge calls returned valid output.

What the hand labels themselves found in the 20 outputs: no blame or labels about the student
in any of them, and a concrete next step in all of them.

## Weak spots

- **The LLM names an "other" case's misconception half the time.** The MaE rows labelled
  `other` (no card fits) are where all the LLM's misses come from. It says `unclear` or picks
  the nearest card: `-5 + (-9)` → `4` and `8 + (-3)` → `-5` came back `unclear` in every run of the final eval,
  and for `12n + 150 = 330` with `12n = 150 - 330` it said `sign_not_changed`. Both are
  defensible, so part of this is the labels. The cases whose card has no rule
  (`two_negatives_make_positive`, `simplify_one_part`, `distribute_first_term_only`) were
  right in every run.
- **"AI only" is the LLM alone, and it can miss one a rule catches:** in earlier runs
  `(4+10)/2` → `9` (`cancel_across_addition`) came back `slip` or `unclear` in some runs; in
  the final run it was right every time. In the product a rule answers it before the LLM.
  "AI only" runs sympy inline (`math_workers=0`, so the patched function is the one called),
  without the worker pool's timeout: its request latencies aren't comparable with the product
  mode's, and none of its 13 cases is near the time limit.
- **The numbers guard never fired (0 of 144 diagnoses, 0 of 78 rule-match moves).** Its blind spot is real, though. It
  checks values, so new math whose value was given passes: "2/3 becomes 4/6, so 4/6 + 1/6 =
  5/6" and "(4/3)*(2/5) rather than (3/4)*(5/2)" were shown in the first run. Both were right,
  but sympy didn't produce them.
- **Transcription scored 100%, so these images are too easy to tell versions apart.** They are
  drawn with a stroke font, not written by people. Treat 100% as an upper bound for real
  teachers' photos; the next step is a set of real handwriting photos (with consent).
- **The prompt cache is best effort.** It covered 66–68% of diagnosis prompt tokens in the latest
  run, 64–85% in the four before and about 60% in earlier ones. The moves call's prompt (680
  tokens) is under the 1024-token caching minimum, like transcription's. Azure caches the stable prefix (system prompt plus topic
  cards, about 1280 tokens). Transcription prompts (482 tokens) are under the 1024-token
  caching minimum.
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
- **`results.yaml`** is pinned by `fingerprint.py`. `run` and `judge` stamp every output row
  with the fingerprint of the code and inputs that made it, and `summarize` refuses rows with
  another stamp, outputs that don't cover every case and image exactly `--runs` times, and any
  `*-partial.jsonl` left by a budget stop. It keeps the recorded recommendation unless
  `--recommend` is given. `judge` reuses scores whose id, text and stamp match, and stops at
  its own `--budget`.
- **`judge.py`** scores the shown AI text with the app's offline `judge` task. Kappa is
  linearly weighted Cohen's kappa over "no" < "to some extent" < "yes". A dimension is quoted
  only at kappa ≥ 0.6.

## Rerun

```sh
make evals    # run (about $2.25), judge (about $1.25), summarize; needs the repo's .env
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
