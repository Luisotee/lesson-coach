import { LIMITS, type LineIn, type MathIn, type ReviewLine } from '@/components/input/types'

/** A line has content when its left side or right side is not blank. */
export const isBlank = (l: ReviewLine) => !l.left.trim() && !l.right.trim()

/** Reviewed lines as the API's steps; blank lines dropped, whitespace trimmed. */
export function toLineIns(lines: ReviewLine[]): LineIn[] {
  return lines
    .filter((l) => !isBlank(l))
    .map((l) => {
      const line: { left: string; right?: string; op?: string } = { left: l.left.trim() }
      if (l.right.trim()) line.right = l.right.trim()
      if (l.op.trim()) line.op = l.op.trim()
      return line
    })
}

/** One reviewed line as one expression: `left = right`, without the margin operation. */
export function toExpression(line: ReviewLine): MathIn {
  const left = line.left.trim()
  const right = line.right.trim()
  // One side alone is that side, never "= 5".
  return { text: left && right ? `${left} = ${right}` : left || right }
}

/** What a typed field holds: LaTeX from MathLive, or text from the fallback field. */
export type FieldValue = { latex: string } | { text: string }

/** Why a value can't be sent; one name per message (`input.type.*`, `input.review.blocked.*`). */
export type Issue = 'tooLong' | 'emptyBox'

/**
 * The one check of the API's limits (backend/app/api/models.py) for a typed value: LaTeX
 * up to 400 characters with no empty MathLive box, text up to 200. Null when it can be sent.
 */
export function mathIssue(v: FieldValue): Issue | null {
  if ('latex' in v) {
    const latex = v.latex.trim()
    if (latex.length > LIMITS.latex) return 'tooLong'
    return latex.includes('\\placeholder') ? 'emptyBox' : null
  }
  return v.text.trim().length > LIMITS.text ? 'tooLong' : null
}

/** The same check for a reviewed line: each side up to 200 characters, the operation up to 30. */
export function lineIssue(l: ReviewLine): Issue | null {
  const long =
    l.left.trim().length > LIMITS.text ||
    l.right.trim().length > LIMITS.text ||
    l.op.trim().length > LIMITS.op
  return long ? 'tooLong' : null
}

/** A typed value as the API's MathIn, or null when it is empty or has an issue. */
export function toMath(v: FieldValue): MathIn | null {
  if (mathIssue(v)) return null
  if ('latex' in v) return v.latex.trim() ? { latex: v.latex.trim() } : null
  return v.text.trim() ? { text: v.text.trim() } : null
}
