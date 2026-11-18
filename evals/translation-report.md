# Translation report

Written by `pipeline/translate.py` with model `gpt-5.5-offline`. Each language's prompts and three packs are translated from the English packs; the math is copied and verified identical (`pipeline/checks.py: translation_findings`). The judge compares each English text with its translation.

Shipped: none. Left out: fr. Total cost: about $6.70.

Judge flag rate: the share of texts a judge majority flagged in any attempt (each flagged text was retried or resampled until it passed, or the language was left out).

| Language | Shipped | Calls (translate / judge) | Retries | Fresh samples | Texts judged | Judge flag rate | Cost |
|---|---|---|---|---|---|---|---|
| fr (French) | no | 41 / 77 | 22 | 0 | 372 | 5.1% | $6.70 |

## fr: left out

- fractions: worked_examples[1].steps[2].explanations.another_way: judge: The translation renders “more than one whole” as “supérieur à un entier,” which means greater than an integer/whole number rather than greater than one whole unit. (This changes the intended meaning; it should convey that the result is greater than one whole (e.g., “supérieur à une unité” or “plus grand que 1”).)
- linear-equations: outline[2].activity: judge: "Keep the focus on the balance step" is mistranslated as "Garder l’attention sur l’étape d’équilibre," which is not idiomatic/clear French for maintaining focus on the balancing step in equation solving. (The phrase "garder l’attention" is unidiomatic here; a native reader may not understand it as intended. It should be something like "Garder l’accent sur l’étape d’équilibrage" or "Mettre l’accent sur...")
- linear-equations: worked_examples[1].steps[0].explanations.another_way: judge: The phrase "on divise tout des deux membres par `5`" is ungrammatical/unnatural French and does not clearly convey dividing the entirety of both sides by 5. (French would require something like "on divise les deux membres par 5" or "on divise chacun des deux membres par 5"; "tout des deux membres" is not grammatical.)
