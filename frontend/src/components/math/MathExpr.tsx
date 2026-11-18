import { useTranslation } from 'react-i18next'
import { renderNode } from '@/components/math/render'
import { cn } from '@/lib/utils'
import { parseMath } from '@/math/parse'
import { speak } from '@/math/speech'
import type { MathNode } from '@/math/types'

/**
 * One handwritten expression from sympy plain text, e.g. `1/2 + 1/3`, or from an already
 * built tree. Screen readers get the spoken text in the active language; the drawing is
 * hidden from them. Always left to right. Text that doesn't parse is shown as written.
 */
export function MathExpr({
  expr,
  node,
  className,
}: { className?: string } & ({ expr: string; node?: never } | { node: MathNode; expr?: never })) {
  const { t } = useTranslation()
  const parsed = node ? { ok: true as const, value: node } : parseMath(expr ?? '')
  const label = parsed.ok ? speak(parsed.value, t) : (expr ?? '')
  return (
    <span
      role="math"
      aria-label={label}
      dir="ltr"
      className={cn('inline-block font-hand whitespace-nowrap', className)}
    >
      <span aria-hidden="true">{parsed.ok ? renderNode(parsed.value) : expr}</span>
    </span>
  )
}
