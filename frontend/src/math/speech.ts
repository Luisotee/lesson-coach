import type { TFunction } from 'i18next'
import { parseLine, parseMath, showsDot, unwrapGroup, type ParsedLine } from '@/math/parse'
import type { MarginOp, MathNode } from '@/math/types'

/**
 * Spoken text for math, in the active language. Every phrase comes from the locale
 * (`math.speech.*`), so a translator controls word order. Numbers stay as digits; screen
 * readers read them in the page language.
 */

const isPlain = (n: MathNode): boolean => n.type === 'num' || n.type === 'var'

const isAtom = (n: MathNode): boolean =>
  isPlain(n) || ((n.type === 'neg' || n.type === 'pos') && isAtom(n.arg))

const isInteger = (n: MathNode): n is { type: 'num'; value: string } =>
  n.type === 'num' && /^\d+$/.test(n.value)

export function speak(node: MathNode, t: TFunction): string {
  const s = (n: MathNode) => speak(n, t)
  const bracketed = (n: MathNode) => t('math.speech.group', { inner: s(n) })
  switch (node.type) {
    case 'num':
      return node.value
    case 'var':
      return node.name
    case 'neg':
      return t('math.speech.negative', { arg: s(node.arg) })
    case 'pos':
      return t('math.speech.positive', { arg: s(node.arg) })
    case 'add':
      return t(node.op === '+' ? 'math.speech.plus' : 'math.speech.minus', {
        left: s(node.left),
        right: s(node.right),
      })
    case 'mul':
      return t(
        showsDot(node.left, node.right) || node.right.type === 'group'
          ? 'math.speech.times'
          : 'math.speech.juxtaposed',
        { left: s(node.left), right: s(node.right) },
      )
    case 'frac': {
      const num = unwrapGroup(node.num)
      const den = unwrapGroup(node.den)
      if (isInteger(num) && isInteger(den) && Number(den.value) >= 2 && Number(den.value) <= 10) {
        return t('math.speech.fractionSimple', { num: Number(num.value), den: Number(den.value) })
      }
      const key = isAtom(num) && isAtom(den) ? 'math.speech.over' : 'math.speech.fraction'
      return t(key, { num: s(num), den: s(den) })
    }
    case 'pow': {
      // (−3)² and −3² differ: a base other than a plain number or letter keeps its brackets.
      const innerBase = unwrapGroup(node.base)
      const base = isPlain(innerBase) ? s(innerBase) : bracketed(innerBase)
      const exp = unwrapGroup(node.exp)
      if (!isPlain(exp)) {
        // 2^(x + 1) vs 2^x + 1: say where a compound exponent ends.
        return t('math.speech.powerGroup', { base, exp: s(exp) })
      }
      const power =
        exp.type === 'num' && exp.value === '2'
          ? 'squared'
          : exp.type === 'num' && exp.value === '3'
            ? 'cubed'
            : 'other'
      return t('math.speech.power', { base, exp: s(exp), power })
    }
    case 'group':
      // "5 minus negative 3": brackets around a lone signed number add nothing when spoken.
      return isAtom(node.inner) ? s(node.inner) : bracketed(node.inner)
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

/** Spoken text for a parsed notebook line: `left = right`, an expression, or `= expression`. */
export function speakParsedLine(line: ParsedLine, continued: boolean, t: TFunction): string {
  const say = (r: ParsedLine['left'], src: string) => (r.ok ? speak(r.value, t) : src)
  const left = say(line.left, line.source.left)
  let spoken: string
  if (line.right)
    spoken = t('math.speech.equals', { left, right: say(line.right, line.source.right) })
  else if (continued) spoken = t('math.speech.continued', { expr: left })
  else spoken = left
  if (!line.op) return spoken
  const op = line.op.ok ? speakOp(line.op.value, t) : line.source.op
  return t('math.speech.lineWithOp', { line: spoken, op })
}

/** Spoken text for one notebook line given as text. */
export function speakLine(
  {
    left,
    right = '',
    op = '',
    continued = false,
  }: { left: string; right?: string; op?: string; continued?: boolean },
  t: TFunction,
): string {
  return speakParsedLine(parseLine({ left, right, op }), continued, t)
}
