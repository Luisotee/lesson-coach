# Pack verification report

Language `en`. Written by `pipeline/verify.py`.

Deterministic checks (sympy, through `app.math`): schema, sources unchanged and not
stale, worked steps equal to sympy's and passing `check_steps`, answers, every number
in a step explanation present in its step, every "`A` is `B`" claim true, prompts.

| Topic | Deterministic findings | Steps explained | Unavailable | Judge flags |
|---|---|---|---|---|
| negative-numbers | 0 | 9/9 | none | 0 |
| fractions | 0 | 10/10 | none | 0 |
| linear-equations | 0 | 10/10 | none | 0 |

## Generation

- LLM calls: {'generate': 18, 'judge': 22}, failed: 0
- Targeted retries: 4; fresh samples: 2
- Judge majorities that flagged a field: {'steps[3]': 1, 'steps[2]': 1}
- Dropped (shipped as unavailable): none
- Tokens: prompt 58741 (cached 2560), completion 25956 (reasoning 0)
- Cost: about $1.06 at $5.0 input, $0.5 cached and $30.0 output per million tokens (reasoning tokens bill as output)

The judge columns come from an independent `verify.py --judge` run.
