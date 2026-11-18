# Translation report

Written by `pipeline/translate.py` with model `gpt-5.5-offline`. Each language's prompts and three packs are translated from the English packs; the math is copied and verified identical (`pipeline/checks.py: translation_findings`). The judge compares each English text with its translation.

Shipped: none. Left out: fr. Total cost: about $5.39.

Judge flag rate: the share of texts a judge majority flagged in any attempt (each flagged text was retried or resampled until it passed, or the language was left out).

| Language | Shipped | Calls (translate / judge) | Retries | Fresh samples | Texts judged | Judge flag rate | Cost |
|---|---|---|---|---|---|---|---|
| fr (French) | no | 51 / 129 | 11 | 21 | 1078 | 12.2% | $5.39 |

## fr: left out

- negative-numbers: questions[4].answer: judge: TR answer starting at 3 and moving seven steps left (“Avance de sept pas vers la gauche” is awkward/contradictory in French because “avance” suggests moving forward; “recule” or “déplace-toi” would be more natural.)
- negative-numbers: misconceptions[2].why_it_feels_right: judge: TR: L'élève a appris qu'ajouter rend les nombres plus grands en taille, et le premier signe est celui qu'il voit d'abord. (« plus grands en taille » is awkward/non-idiomatic in French for mathematical magnitude; « plus grands en valeur absolue » or similar would be more natural.)
- negative-numbers: misconceptions[2].what_to_say.probe: judge: TR: Si tu pars de `-5` et que tu avances de trois pas, dans quel sens vas-tu ? (“move three steps” is neutral, but « avances » can imply moving forward/right rather than simply moving three steps; it risks changing the intended prompt.)
- fractions: why_it_works: judge: TR: On ne peut additionner que des parts de même nature. (“de même nature” is less precise/idiomatic for “like parts” here; “parts de même taille” would better match the mathematical point.); judge: TR: La division demande combien de fois le diviseur tient dedans. (“tient dedans” is awkward/incomplete in French because it does not state what the divisor fits into; better: “combien de fois le diviseur tient dans le dividende/la quantité.”)
- fractions: questions[4].answer: judge: TR: Une barre de fraction indique que tout le numérateur est divisé par le dénominateur. (The English says the fraction bar divides the whole top. The translation adds “by the denominator,” which is mathematically true but slightly more specific than the source; acceptable in meaning, but it also shifts from the structural warning about the whole top expression to a definition of the fraction bar.)
- fractions: outline[4].activity: judge: TR: Utiliser la question « Combien tiennent dedans ? » (Awkward/incomplete French; it omits what fits into what. A clearer rendering would be “Combien y en a-t-il dedans ?” or “Combien de fois cela tient-il dedans ?”)
- fractions: questions[0].answer: judge: TR: « Les demis et les tiers » (« Les demis » is awkward for equal parts; « les moitiés et les tiers » would be more natural.)
- fractions: outline[2].activity: judge: TR: « les demis et les tiers » (« Les demis » is awkward here; « les moitiés et les tiers » is the natural phrasing for halves and thirds as parts.)
- fractions: misconceptions[1].what_to_say.probe: judge: `6/15` est-il plus grand que `2/5`, plus petit, ou égal ? Que devraient faire trois paquets de `2/5` ? (“Que devraient faire” is ungrammatical/awkward and changes the sense; it should ask what three lots of 2/5 should be, e.g. “Que devraient valoir/représenter trois paquets de 2/5 ?”)
- fractions: misconceptions[3].belief: judge: On peut simplifier un nombre du numérateur avec un nombre du dénominateur, même à travers un signe plus. (“Simplifier un nombre ... avec un nombre ...” is awkward/unusual for cancellation; a more natural math phrasing would be “simplifier/annuler un facteur du numérateur avec un facteur du dénominateur”. Also “à travers un signe plus” is a literal calque; “malgré un signe plus” or “de part et d’autre d’un signe plus” would be more natural depending on the intended structure.)
- linear-equations: summary: judge: TR: Résoudre des équations linéaires en effectuant la même opération aux deux membres et en vérifiant la réponse. (« effectuer une opération aux deux membres » est awkward; on dirait plutôt « sur les deux membres » ou « appliquer la même opération aux deux membres ».)
- linear-equations: idea: judge: TR: ... S’il y a des parenthèses, on considère que toute la parenthèse est multipliée. ... (« toute la parenthèse est multipliée » est maladroit/incomplet en français; il faudrait préciser qu’elle est multipliée par le facteur extérieur.)
- linear-equations: questions[5].answer: judge: TR: On remplace l’inconnue par la réponse dans l’équation de départ. Si les deux côtés sont égaux, la réponse convient. (« côtés » est moins approprié dans ce contexte mathématique que « membres », utilisé ailleurs; terme inhabituel pour les deux côtés d’une équation en français scolaire.)
- linear-equations: worked_examples[1].steps[0].explanations.another_way: judge: The translation says “on divise tout chacun des deux membres par 5”. (Awkward/ungrammatical French. A natural rendering would be “on divise chacun des deux membres par 5” or “on divise les deux membres entiers par 5”.)
- linear-equations: misconceptions[0].why_it_feels_right: judge: « déplacer signifie soustraire » (Too absolute/awkward: moving terms across an equals sign does not always mean subtracting; the English refers specifically to this shortcut in the +6 context.)
