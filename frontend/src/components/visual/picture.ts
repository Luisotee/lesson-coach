import { fractionOf, integerOf, parseSide, termsOf, type Term } from '@/math/terms'
import type { Step } from '@/math/types'

/** At most this many x tiles; a bigger coefficient is one labelled tile. */
export const MAX_TILES = 6

export type Picture =
  | { kind: 'balance'; left: Term[]; right: Term[] }
  | { kind: 'bars'; terms: { sign: 1 | -1; num: number; den: number }[] }
  | { kind: 'counters'; terms: { sign: 1 | -1; n: number }[] }

const MAX_DEN = 12
const MAX_COUNTERS = 10

export function pictureFor(step: Pick<Step, 'left' | 'right'>): Picture | null {
  const left = parseSide(step.left)
  if (!left) return null
  if (step.right) {
    const right = parseSide(step.right)
    return right ? { kind: 'balance', left: termsOf(left), right: termsOf(right) } : null
  }
  const terms = termsOf(left)
  const fracs = terms.map((t) => ({ sign: t.sign, f: fractionOf(t.node) }))
  if (fracs.every((x) => x.f && x.f.den <= MAX_DEN && x.f.num <= 3 * x.f.den)) {
    return { kind: 'bars', terms: fracs.map((x) => ({ sign: x.sign, ...x.f! })) }
  }
  const ints = terms.map((t) => ({ sign: t.sign, n: integerOf(t.node) }))
  if (ints.every((x) => x.n !== null && Math.abs(x.n) <= MAX_COUNTERS)) {
    return {
      kind: 'counters',
      // Fold a term's own sign (−(−3)) into the counters' colour, keep the written operator.
      terms: ints.map((x) => ({ sign: x.sign, n: x.n! })),
    }
  }
  return null
}
