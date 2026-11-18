import type { TFunction } from 'i18next'
import { parseMath, parseOp, showsDot } from '@/math/parse'
import type { MarginOp, MathNode } from '@/math/types'

/**
 * Spoken text for math, in the active language. Every phrase comes from the locale
 * (`math.speech.*`), so a translator controls word order. Numbers stay as digits; screen
 * readers read them in the page language.
 */

const isAtom = (n: MathNode): boolean =>
  n.type === 'num' || n.type === 'var' || (n.type === 'neg' && isAtom(n.arg))

const isInteger = (n: MathNode): n is { type: 'num'; value: string } =>
  n.type === 'num' && /^\d+$/.test(n.value)

/** Strips the parentheses that a stacked fraction or an exponent makes unnecessary. */
const unwrap = (n: MathNode): MathNode => (n.type === 'group' ? n.inner : n)

export function speak(node: MathNode, t: TFunction): string {
  const s = (n: MathNode) => speak(n, t)
  switch (node.type) {
    case 'num':
      return node.value
    case 'var':
      return node.name
    case 'neg':
      return t('math.speech.negative', { arg: s(node.arg) })
    case 'add':
      return t(node.op === '+' ? 'math.speech.plus' : 'math.speech.minus', {
        left: s(node.left),
        right: s(node.right),
      })
    case 'mul':
      return t(showsDot(node.left, node.right) || node.right.type === 'group' ? 'math.speech.times' : 'math.speech.juxtaposed', {
        left: s(node.left),
        right: s(node.right),
      })
    case 'frac': {
      const num = unwrap(node.num)
      const den = unwrap(node.den)
      if (isInteger(num) && isInteger(den) && Number(den.value) >= 2 && Number(den.value) <= 10) {
        return t('math.speech.fractionSimple', { num: Number(num.value), den: Number(den.value) })
      }
      const key = isAtom(num) && isAtom(den) ? 'math.speech.over' : 'math.speech.fraction'
      return t(key, { num: s(num), den: s(den) })
    }
    case 'pow': {
      const exp = unwrap(node.exp)
      const power = exp.type === 'num' && exp.value === '2' ? 'squared' : exp.type === 'num' && exp.value === '3' ? 'cubed' : 'other'
      return t('math.speech.power', { base: s(node.base), exp: s(exp), power })
    }
    case 'group':
      return isAtom(node.inner) ? s(node.inner) : t('math.speech.group', { inner: s(node.inner) })
    case 'rel':
      return node.sides.map(s).reduce((left, right) => t('math.speech.equals', { left, right }))
  }
}

export function speakOp(op: MarginOp, t: TFunction): string {
  return t(`math.op.${op.kind}`, { arg: speak(op.arg, t) })
}

/** Spoken text for a plain-text expression; unparseable text is read as written. */
export function speakText(src: string, t: TFunction): string {
  const parsed = parseMath(src)
  return parsed.ok ? speak(parsed.value, t) : src
}

/** Spoken text for one notebook line: `left = right`, an expression, or `= expression`. */
export function speakLine(
  { left, right, op, continued = false }: { left: string; right?: string; op?: string; continued?: boolean },
  t: TFunction,
): string {
  let line: string
  if (right) line = t('math.speech.equals', { left: speakText(left, t), right: speakText(right, t) })
  else if (continued) line = t('math.speech.continued', { expr: speakText(left, t) })
  else line = speakText(left, t)
  if (!op) return line
  const parsedOp = parseOp(op)
  return t('math.speech.lineWithOp', { line, op: parsedOp.ok ? speakOp(parsedOp.value, t) : op })
}
