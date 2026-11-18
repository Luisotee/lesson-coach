# Translation report

Written by `pipeline/translate.py` with model `gpt-5.5-offline`. Each language's prompts and three packs are translated from the English packs; the math is copied and verified identical (`pipeline/checks.py: translation_findings`). The judge compares each English text with its translation.

Shipped: de, el, pt, pt-BR, ru, es, sv, pl. Left out: fr, ar, it, kk. Total cost: about $21.27.

Judge flag rate: the share of texts a judge majority flagged in any attempt (each flagged text was retried or resampled until it passed, or the language was left out).

| Language | Shipped | Calls (translate / judge) | Retries | Fresh samples | Texts judged | Judge flag rate | Cost |
|---|---|---|---|---|---|---|---|
| fr (French) | no | 38 / 60 | 19 | 0 | 368 | 3.5% | $7.91 |
| ar (Arabic (Modern Standard Arabic)) | no | 38 / 70 | 19 | 0 | 376 | 5.9% | $1.32 |
| de (German) | yes | 36 / 66 | 17 | 0 | 371 | 4.0% | $1.24 |
| el (Greek) | yes | 34 / 58 | 15 | 0 | 368 | 3.3% | $1.30 |
| it (Italian) | no | 35 / 73 | 16 | 0 | 371 | 4.3% | $1.29 |
| pt (European Portuguese) | yes | 32 / 60 | 13 | 0 | 368 | 3.3% | $1.13 |
| pt-BR (Brazilian Portuguese) | yes | 31 / 59 | 12 | 0 | 368 | 3.3% | $1.14 |
| ru (Russian) | yes | 32 / 51 | 13 | 0 | 368 | 3.3% | $1.13 |
| es (Spanish) | yes | 32 / 50 | 13 | 0 | 364 | 2.2% | $1.01 |
| sv (Swedish) | yes | 31 / 51 | 12 | 0 | 368 | 3.3% | $1.10 |
| pl (Polish) | yes | 36 / 70 | 17 | 0 | 379 | 6.1% | $1.43 |
| kk (Kazakh (Cyrillic script)) | no | 31 / 59 | 12 | 0 | 371 | 4.6% | $1.28 |

## fr: left out

- fractions: worked_examples[2].steps[3].explanations.another_way: spans_changed: the math spans differ from the English; number_not_in_source: ['1'] not in the English

## ar: left out

- linear-equations: worked_examples[2].steps[2].explanations.another_way: spans_changed: the math spans differ from the English
- linear-equations: worked_examples[2].steps[2].explanations.visual: spans_changed: the math spans differ from the English

## it: left out

- linear-equations: outline[2].activity: judge: “Keep the focus on the balance step” is translated as “Mantieni l’attenzione sul passaggio di equilibrio.” (In Italian math teaching, “balance step” here refers to maintaining equation balance by applying the same operation to both sides; “passaggio di equilibrio” is not a standard or clear term and may not be understood as intended.)

## kk: left out

- linear-equations: misconceptions[1].what_to_say.probe: judge: TR uses “two-ға” instead of the Kazakh Cyrillic “екіге” for “by two”. (The translation leaves the English word “two” in Latin script with a Kazakh suffix, which is not proper Kazakh Cyrillic and is ungrammatical/nonnative in this teaching context.)
- linear-equations: misconceptions[1].what_to_say.nudge: judge: TR uses “two-ға” instead of the Kazakh Cyrillic “екіге” for “by two”. (The translation leaves the English word “two” in Latin script with a Kazakh suffix, which is not proper Kazakh Cyrillic and is ungrammatical/nonnative in this teaching context.)
