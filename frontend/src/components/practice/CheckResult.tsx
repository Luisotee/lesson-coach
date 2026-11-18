import { CircleCheck, CircleHelp, TriangleAlert } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import type { CheckWorkingResult } from '@/api/types'
import { EquationLine, Notebook } from '@/components/math'
import { toSteps } from '@/math/lines'
import { isContinued } from '@/math/parse'

/**
 * What "Check my working" found, privately: every line follows, or which line first doesn't.
 * sympy decides; nothing is scored or kept.
 */
export function CheckResult({ result }: { result: CheckWorkingResult }) {
  const { t } = useTranslation()
  const bad = result.first_bad_line
  const lines = toSteps(result.lines)
  return (
    <div
      className="flex flex-col gap-3 rounded-2xl border border-line bg-white p-4"
      data-check={result.status}
    >
      {result.status === 'all_follow' && (
        <p className="flex items-start gap-2 font-semibold text-green-text">
          <CircleCheck aria-hidden="true" className="mt-0.5 size-5 flex-none text-green" />
          <span>
            {t('practice.allFollow')}{' '}
            {result.final && (
              <span className="font-normal">{t(`practice.final.${result.final}`)}</span>
            )}
          </span>
        </p>
      )}
      {result.status === 'line_doesnt_follow' && bad && (
        <p className="flex items-start gap-2 font-semibold text-mark">
          <TriangleAlert aria-hidden="true" className="mt-0.5 size-5 flex-none" />
          <span>
            {t('practice.lineDoesntFollow', { n: bad.index + 1 })}{' '}
            <span className="font-normal text-navy">{t(`practice.badReason.${bad.reason}`)}</span>
          </span>
        </p>
      )}
      {(result.status === 'unclear' || result.status === 'out_of_scope') && (
        <p className="flex items-start gap-2">
          <CircleHelp aria-hidden="true" className="mt-0.5 size-5 flex-none" />
          <span>
            {t(`practice.status.${result.status}`)}
            {result.reason && <> {t(`mistake.reason.${result.reason}`)}</>}
          </span>
        </p>
      )}
      {lines.length > 0 && (
        <Notebook label={t('practice.yourLines')} pen="pencil" numbered>
          {lines.map((l, i) => (
            <EquationLine
              key={i}
              index={i}
              left={l.left}
              right={l.right}
              op={l.op}
              continued={isContinued(lines, i)}
              annotate={bad && bad.index === i ? { circle: true } : undefined}
            />
          ))}
        </Notebook>
      )}
    </div>
  )
}
