# Content attribution

## Our content (CC BY 4.0)

The source lessons (`content/source/*.md`), the misconceptions (`content/source/*.misconceptions.json`), the practice prompts and the reworded hints are Lesson Coach's own writing, under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).

They were drafted with AI (Claude Code) and await human review. Every field written by AI is listed in the item's `ai_generated` array. `backend/tests/test_content.py` uses sympy to check every answer, every misconception's example wrong answer, and inline claims written as "`A` is `B`" or "`A` = `B`" (for example "`5 - (-3)` is `8`"). Every other inline expression, including the equation lines in hints, is only checked to parse; checking each step is planned for the pipeline's `verify.py`. The misconception sentences that state a wrong answer on purpose are only parsed.

## Practice problems: OATutor-Content and OpenStax (CC BY 4.0)

`content/practice/*.json` adapts 24 problem steps from [OATutor-Content](https://github.com/CAHLR/OATutor-Content) at commit `08ef4819889e70835e86926f84037e79141652f3`, under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
- **Problems** are curated by the OATutor project from OpenStax [Elementary Algebra 2e](https://openstax.org/details/books/elementary-algebra-2e) and [Intermediate Algebra 2e](https://openstax.org/details/books/intermediate-algebra-2e) (CC BY 4.0, © Rice University).
- **Hints** are by the [OATutor project](https://www.oatutor.io/) (CC BY 4.0).
- **Per item:** each item's `source` gives the file path and URL at that commit, the OpenStax book, the license and what we changed.
- **What we changed, in every item:**
  - took one step of the problem;
  - converted the LaTeX to plain sympy text;
  - wrote our own prompt;
  - condensed and reworded the hints into four rungs (goal, information, computation, answer).
- **Missing license field:** two source problems (`a623746multistep2` and `a623746multistep8`) have an empty `license` field in their JSON. The repository as a whole is CC BY 4.0, which we rely on.

## Eval seed: MaE (MIT)

`evals/mistakes.yaml` adapts 16 examples from MaE, the [Math Misconceptions and Errors dataset](https://github.com/nancyotero-projects/math-misconceptions), at commit `12bee142d49dfb3c874149035cfbad28547a818b`. The dataset accompanies Otero, Druga and Lan, [A Benchmark for Math Misconceptions](https://arxiv.org/abs/2412.03765).

We changed the numbers in every row, rewrote the problems as sympy text and mapped each row to our misconception ids. Each row's `source` names the MaE misconception and example. The MaE license:

```
MIT License

Copyright (c) 2024 Nancy Otero

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

## Akelius Math (links only)

Each lesson's front matter links to the matching lesson in [Akelius Math](https://akelius.education/math/en). We found the lesson URLs with the site's own search. We copied only lesson titles and URLs, no content: Akelius Math states no license.
