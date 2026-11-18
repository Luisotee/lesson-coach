import { useTranslation } from 'react-i18next'
import { MathExpr } from '@/components/math/MathExpr'
import { substituteAnswer } from '@/math/substitute'

/**
 * "check: 3 · 5 + 5 = 20" under a solved equation, with a hand-drawn tick. The answer is the
 * pack's sympy-verified one; this only writes it into the equation. Renders nothing when the
 * problem isn't a single-variable equation.
 */
export function CheckLine({ equation, answer }: { equation: string; answer: string }) {
  const { t } = useTranslation()
  const node = substituteAnswer(equation, answer)
  if (!node) return null
  return (
    <p
      dir="ltr"
      className="mt-2.5 flex w-fit items-center gap-2.5 border-t-2 border-navy pt-2.5 font-hand text-xl text-pen-green"
    >
      <span>{t('topic.check')}</span>
      <MathExpr node={node} />
      <svg
        width="30"
        height="26"
        viewBox="0 0 30 26"
        fill="none"
        stroke="currentColor"
        strokeWidth="3"
        strokeLinecap="round"
        strokeLinejoin="round"
        role="img"
        aria-label={t('topic.checkHolds')}
      >
        <path
          d="M3 14c3 2 5 5 7 9 4-9 9-15 17-20"
          pathLength={1}
          className="[stroke-dasharray:1] motion-safe:animate-[draw_0.6s_ease-out_both]"
        />
      </svg>
    </p>
  )
}
