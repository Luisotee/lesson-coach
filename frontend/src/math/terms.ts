import { parseMath, unwrapGroup } from '@/math/parse'
import type { MathNode } from '@/math/types'

/** One term of a sum as written, with its sign: `3*x - 5` → [+3x, −5]. */
export interface Term {
  sign: 1 | -1
  node: MathNode
}

/** Splits a sum into its written terms. A leading minus becomes the term's sign. */
export function termsOf(node: MathNode): Term[] {
  if (node.type === 'add') {
    const right = termsOf(node.right)
    return [
      ...termsOf(node.left),
      ...(node.op === '+' ? right : right.map((t) => ({ ...t, sign: (t.sign * -1) as 1 | -1 }))),
    ]
  }
  if (node.type === 'neg')
    return termsOf(node.arg).map((t) => ({ ...t, sign: (t.sign * -1) as 1 | -1 }))
  return [{ sign: 1, node }]
}

const INT = /^\d+$/

/** `n` for an integer literal, else null. */
export function integerOf(node: MathNode): number | null {
  const n = unwrapGroup(node)
  if (n.type === 'num' && INT.test(n.value)) return Number(n.value)
  if (n.type === 'neg') {
    const inner = integerOf(n.arg)
    return inner === null ? null : -inner
  }
  if (n.type === 'pos') return integerOf(n.arg)
  return null
}

/** `{num, den}` for an integer fraction such as `3/4`, else null. */
export function fractionOf(node: MathNode): { num: number; den: number } | null {
  const n = unwrapGroup(node)
  if (n.type !== 'frac') return null
  const num = integerOf(n.num)
  const den = integerOf(n.den)
  return num !== null && den !== null && num >= 0 && den > 0 ? { num, den } : null
}

/** `{coef, name}` for `x`, `3*x` or `3x`, else null. */
export function variableTermOf(node: MathNode): { coef: number; name: string } | null {
  if (node.type === 'var') return { coef: 1, name: node.name }
  if (node.type === 'mul' && node.right.type === 'var') {
    const coef = integerOf(node.left)
    if (coef !== null && coef > 0) return { coef, name: node.right.name }
  }
  return null
}

export function parseSide(src: string): MathNode | null {
  const parsed = parseMath(src)
  return parsed.ok && parsed.value.type !== 'rel' ? parsed.value : null
}
