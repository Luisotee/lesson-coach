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

- LLM calls: {'generate': 16, 'judge': 12}, failed: 0
- Targeted retries: 4; fresh samples: 0
- Judge majorities that flagged a field: {}
- Dropped (shipped as unavailable): none
- Tokens: prompt 40045 (cached 1280), completion 17740 (reasoning 0)
- Cost: about $0.73 at $5.0 input, $0.5 cached and $30.0 output per million tokens (reasoning tokens bill as output)

The judge columns come from an independent `verify.py --judge` run.
