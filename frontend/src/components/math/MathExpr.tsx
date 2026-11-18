import { useTranslation } from 'react-i18next'
import { renderNode } from '@/components/math/render'
import { cn } from '@/lib/utils'
import { parseMath } from '@/math/parse'
import { speak } from '@/math/speech'

/**
 * One handwritten expression from sympy plain text, e.g. `1/2 + 1/3`. Screen readers get the
 * spoken text in the active language; the drawing is hidden from them. Always left to right.
 */
export function MathExpr({ expr, className }: { expr: string; className?: string }) {
  const { t } = useTranslation()
  const parsed = parseMath(expr)
  const label = parsed.ok ? speak(parsed.value, t) : expr
  return (
    <span
      role="math"
      aria-label={label}
      dir="ltr"
      className={cn('font-hand inline-block whitespace-nowrap', className)}
    >
      <span aria-hidden="true">{parsed.ok ? renderNode(parsed.value) : expr}</span>
    </span>
  )
}
