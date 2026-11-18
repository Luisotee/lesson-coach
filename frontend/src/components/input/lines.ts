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

/** True when MathLive still shows an empty box (e.g. a fraction with no denominator yet). */
export const hasEmptyBox = (latex: string) => latex.includes('\\placeholder')

/** A typed LaTeX value, or null when empty, unfinished or over the API's limit. */
export function latexValue(latex: string): MathIn | null {
  const v = latex.trim()
  if (!v || v.length > LIMITS.latex || hasEmptyBox(v)) return null
  return { latex: v }
}

/** A plain-text value (the fallback field), or null when empty or over the limit. */
export function textValue(text: string): MathIn | null {
  const v = text.trim()
  if (!v || v.length > LIMITS.text) return null
  return { text: v }
}
