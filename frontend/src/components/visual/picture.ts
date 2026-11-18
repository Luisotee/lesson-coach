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
  // A bar is a positive amount; a leading minus has no bar picture, so show the caption only.
  const leadingMinus = terms[0]?.sign === -1
  const fracs = terms.map((t) => ({ sign: t.sign, f: fractionOf(t.node) }))
  if (!leadingMinus && fracs.every((x) => x.f && x.f.den <= MAX_DEN && x.f.num <= 3 * x.f.den)) {
    return { kind: 'bars', terms: fracs.map((x) => ({ sign: x.sign, ...x.f! })) }
  }
  const ints = terms.map((t) => ({ sign: t.sign, n: integerOf(t.node) }))
  if (ints.every((x) => x.n !== null && Math.abs(x.n) <= MAX_COUNTERS)) {
    return {
      kind: 'counters',
      // Between terms the sign is the written operator and `n` is the term's own value, so
      // 5 − (−3) keeps its −. The first term has no operator, so its sign goes into `n`: −5 + 3
      // is five negative counters, then three positive ones.
      terms: ints.map((x, k) =>
        k === 0 ? { sign: 1 as const, n: x.sign * x.n! } : { sign: x.sign, n: x.n! },
      ),
    }
  }
  return null
}
