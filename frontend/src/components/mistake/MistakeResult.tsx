import { ArrowRight, BadgeCheck, CircleCheck, Sparkles } from 'lucide-react'
import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router'
import { useTopicTitle } from '@/api/queries'
import type { Diagnosis, MistakeResult as Result } from '@/api/types'
import { EquationLine, MathExpr, Notebook, StepsNotebook } from '@/components/math'
import { InLang } from '@/components/ContentLang'
import { RichText } from '@/components/RichText'
import { StepPicture } from '@/components/visual/StepPicture'
import { pictureFor } from '@/components/visual/picture'
import { toSteps } from '@/math/lines'
import { isContinued } from '@/math/parse'
import type { Step } from '@/math/types'

function Card({
  children,
  className = '',
  ...rest
}: {
  children: ReactNode
  className?: string
  'data-status'?: string
}) {
  return (
    <div
      {...rest}
      className={`flex flex-col gap-4 rounded-[20px] border border-line bg-white p-5 sm:p-6 ${className}`}
    >
      {children}
    </div>
  )
}

function Figure({ caption, children }: { caption: string; children: ReactNode }) {
  return (
    <figure className="flex min-w-0 flex-[1_1_260px] flex-col gap-2">
      <figcaption className="text-xs font-semibold text-muted-foreground lowercase">
        {caption}
      </figcaption>
      {children}
    </figure>
  )
}

/**
 * The student's lines in pencil, with sympy's first line that doesn't follow circled.
 * Without working, the problem and their answer. With `diagnosed`, the answer is circled when
 * sympy found no line, and the diagnosis's margin note is shown; an abstain gets neither.
 */
function WhatTheyWrote({ result, diagnosed }: { result: Result; diagnosed: boolean }) {
  const { t } = useTranslation()
  const working = toSteps(result.working)
  const circle = diagnosed
  const note = diagnosed ? (result.diagnosis?.margin_note ?? undefined) : undefined
  let lines: Step[]
  let marked: number | null
  if (working.length) {
    lines = working
    marked = result.first_bad_line?.index ?? (circle ? working.length - 1 : null)
  } else if (result.problem?.kind === 'solve' || !result.problem) {
    lines = result.student_answer ? [{ left: result.student_answer, right: '', op: '' }] : []
    marked = circle ? 0 : null
  } else {
    lines = [
      { left: result.problem.expr, right: '', op: '' },
      ...(result.student_answer ? [{ left: result.student_answer, right: '', op: '' }] : []),
    ]
    marked = circle && lines.length > 1 ? 1 : null
  }
  if (!lines.length) return null
  return (
    <Figure caption={t('mistake.whatTheyWrote')}>
      <InLang lang={result.diagnosis?.lang}>
        <Notebook label={t('mistake.whatTheyWrote')} pen="pencil">
          {lines.map((l, i) => (
            <EquationLine
              key={i}
              index={i}
              left={l.left}
              right={l.right}
              op={l.op}
              continued={isContinued(lines, i)}
              annotate={marked === i ? { circle: true, note } : undefined}
            />
          ))}
        </Notebook>
      </InLang>
    </Figure>
  )
}

function WorkedOut({ result }: { result: Result }) {
  const { t } = useTranslation()
  const steps = toSteps(result.worked_solution)
  if (!steps.length) return null
  const last = steps[steps.length - 1]
  const bars = pictureFor(last)?.kind === 'bars'
  return (
    <Figure caption={t('mistake.workedOut')}>
      <StepsNotebook steps={steps} label={t('mistake.workedOut')} pen="green" />
      {bars && <StepPicture step={last} caption={t('mistake.barCaption')} />}
    </Figure>
  )
}

function WhatToSay({ d }: { d: Diagnosis }) {
  const { t } = useTranslation()
  const rows = [
    ['ask', d.what_to_say.probe],
    ['nudge', d.what_to_say.nudge],
    ['tell', d.what_to_say.tell],
  ] as const
  return (
    <Card>
      <h3 className="text-lg font-semibold">{t('mistake.whatToSay')}</h3>
      {d.say_example && (
        <p className="flex flex-wrap items-center gap-2 text-[15px]" data-say-example>
          {t('mistake.sayExample')}
          <MathExpr expr={d.say_example.expr} className="text-xl" />
        </p>
      )}
      {d.say_answer && (
        <p className="flex flex-wrap items-center gap-2 text-[15px]" data-say-answer>
          {t('mistake.sayAnswer')}
          <MathExpr expr={d.say_answer} className="text-xl" />
        </p>
      )}
      {d.source === 'rule' && d.say_source === 'ai' && (
        <p className="text-[13px] text-muted-foreground" data-say-worded>
          {t('mistake.sayWorded')}
        </p>
      )}
      <ol className="flex flex-col gap-3">
        {rows.map(([key, text]) => (
          <li key={key} className="flex flex-col gap-1 sm:flex-row sm:gap-3">
            <span className="w-24 flex-none text-sm font-semibold text-link-ink lowercase">
              {t(`mistake.say.${key}`)}
            </span>
            <InLang lang={d.lang}>
              <RichText text={text} className="text-[15px] leading-relaxed" />
            </InLang>
          </li>
        ))}
      </ol>
    </Card>
  )
}

function TryNext({ d, topic }: { d: Diagnosis; topic?: string }) {
  const { t } = useTranslation()
  const titleOf = useTopicTitle()
  if (!d.try_next) return null
  const body = (
    <>
      <span className="flex flex-col gap-1">
        <span className="text-xs font-semibold text-muted-foreground lowercase">
          {t('mistake.tryNext')}
        </span>
        <span className="flex flex-wrap items-center gap-2">
          <InLang lang={d.cards_lang}>
            <RichText text={d.try_next.prompt} />
          </InLang>
          <MathExpr expr={d.try_next.problem.expr} className="text-2xl" />
        </span>
      </span>
      {topic && (
        <span className="inline-flex items-center gap-2 font-semibold text-link-ink">
          {t('mistake.fromTopic', { topic: titleOf(topic) })}
          <ArrowRight aria-hidden="true" className="size-4 rtl:-scale-x-100" />
        </span>
      )}
    </>
  )
  const cls =
    'flex flex-wrap items-center justify-between gap-3 rounded-[20px] border border-line bg-white p-5 text-navy no-underline'
  return topic ? (
    <Link to={`/topics/${topic}#mistakes`} className={`${cls} hover:border-line-strong`}>
      {body}
    </Link>
  ) : (
    <div className={cls}>{body}</div>
  )
}

function SourceBadge({ d }: { d: Diagnosis }) {
  const { t } = useTranslation()
  return d.source === 'rule' && d.rule_checked ? (
    <span className="inline-flex items-center gap-1.5 rounded-full bg-[#ecfdf5] px-3 py-1 text-[13px] font-semibold text-green-text">
      <BadgeCheck aria-hidden="true" className="size-4" />
      {t('mistake.ruleBadge')}
    </span>
  ) : (
    <span className="inline-flex items-center gap-1.5 rounded-full bg-[#fffbeb] px-3 py-1 text-[13px] font-semibold text-[#92400e]">
      <Sparkles aria-hidden="true" className="size-4" />
      {t('mistake.aiBadge')}
    </span>
  )
}

/** Why the coach abstained or held something back, when it says. */
function Reason({ result }: { result: Result }) {
  const { t } = useTranslation()
  return result.reason ? (
    <p className="text-[15px]" data-reason={result.reason}>
      {t(`mistake.reason.${result.reason}`)}
    </p>
  ) : null
}

/** The first named misconception with a card, if any. */
function namedCards(d: Diagnosis | null) {
  return (d?.misconceptions ?? []).filter((m) => m.id !== 'other' && m.belief)
}

/** The result of "Explain this", for every status the API can return. */
export function MistakeResult({
  result,
  topic,
  onTryAnother,
}: {
  result: Result
  topic?: string
  onTryAnother: () => void
}) {
  const { t } = useTranslation()
  const d = result.diagnosis
  const cards = namedCards(d)

  const tryAnother = (
    <button
      type="button"
      onClick={onTryAnother}
      className="inline-flex min-h-11 items-center self-start rounded-xl border border-line bg-white px-4 font-semibold text-navy hover:bg-[#eef1f4]"
    >
      {t('mistake.tryAnother')}
    </button>
  )

  if (result.status === 'correct' || result.status === 'not_simplified') {
    const same =
      result.status === 'not_simplified' && result.student_answer && result.correct_answer
    return (
      <Card className="items-start" data-status={result.status}>
        <span className="flex size-11 items-center justify-center rounded-full bg-[#ecfdf5]">
          <CircleCheck aria-hidden="true" className="size-6 text-green" />
        </span>
        <h2 className="text-2xl font-semibold">{t('mistake.right')}</h2>
        {same && (
          <Notebook label={t('mistake.sameAmount')} pen="green" className="w-full">
            <EquationLine left={result.student_answer!} right={result.correct_answer!} />
          </Notebook>
        )}
        <p className="text-[15px] leading-relaxed">
          {result.status === 'not_simplified' ? t('mistake.notSimplified') : t('mistake.correct')}
        </p>
        {d && (
          <InLang lang={d.lang}>
            <RichText as="p" text={d.explanation} className="text-[15px] leading-relaxed" />
          </InLang>
        )}
        <Reason result={result} />
        {tryAnother}
      </Card>
    )
  }

  if (result.status === 'diagnosed' || result.status === 'slip') {
    const main = cards[0]
    return (
      <div className="flex flex-col gap-4" data-status={result.status}>
        <Card>
          <div className="flex flex-wrap items-center justify-between gap-2">
            <span className="text-xs font-semibold text-muted-foreground lowercase">
              {result.status === 'slip' ? t('mistake.looksLikeSlip') : t('mistake.likelyReason')}
            </span>
            {d && <SourceBadge d={d} />}
          </div>
          <h2 className="text-2xl leading-snug font-semibold">
            {result.status === 'slip' ? (
              t('mistake.slipTitle')
            ) : main?.belief ? (
              <InLang lang={d?.cards_lang}>
                <RichText text={main.belief} />
              </InLang>
            ) : d ? (
              <InLang lang={d.lang}>
                <RichText text={d.explanation} />
              </InLang>
            ) : (
              t('mistake.reasonUnavailable')
            )}
          </h2>
          <div className="flex flex-wrap gap-4">
            <WhatTheyWrote result={result} diagnosed />
            <WorkedOut result={result} />
          </div>
          {main?.why_it_feels_right && (
            <p className="text-[15px] leading-relaxed">
              <b>{t('topic.whyItFeelsRight')}</b>{' '}
              <InLang lang={d?.cards_lang}>
                <RichText text={main.why_it_feels_right} />
              </InLang>
            </p>
          )}
          {/* On the rule path the explanation is the card's belief and why it feels right,
              both shown above. */}
          {d && d.source !== 'rule' && (main || result.status === 'slip') && (
            <InLang lang={d.lang}>
              <RichText as="p" text={d.explanation} className="text-[15px] leading-relaxed" />
            </InLang>
          )}
          <Reason result={result} />
        </Card>
        {d && <WhatToSay d={d} />}
        {d && <TryNext d={d} topic={topic} />}
        {tryAnother}
      </div>
    )
  }

  if (result.status === 'unclear') {
    return (
      <div className="flex flex-col gap-4" data-status={result.status}>
        <Card>
          <span className="text-xs font-semibold text-muted-foreground lowercase">
            {t('mistake.notSure')}
          </span>
          <h2 className="text-2xl font-semibold">{t('mistake.askHow')}</h2>
          <Reason result={result} />
          {d && (
            <InLang lang={d.lang}>
              <RichText as="p" text={d.explanation} className="text-[15px] leading-relaxed" />
            </InLang>
          )}
          {cards.length > 0 && (
            <div className="flex flex-col gap-2 rounded-xl bg-ground p-4">
              <span className="text-xs font-semibold text-muted-foreground lowercase">
                {t('mistake.possibilities', { count: cards.length })}
              </span>
              {cards.map((m, i) => (
                <p key={m.id}>
                  <b>{i === 0 ? t('mistake.possibly') : t('mistake.or')}</b>{' '}
                  <InLang lang={d?.cards_lang}>
                    <RichText text={m.belief!} />
                  </InLang>
                </p>
              ))}
            </div>
          )}
          <WhatTheyWrote result={result} diagnosed={false} />
        </Card>
        {d && <WhatToSay d={d} />}
        {tryAnother}
      </div>
    )
  }

  // out_of_scope
  return (
    <div className="flex flex-col gap-4" data-status={result.status}>
      <Card>
        <h2 className="text-2xl font-semibold">{t('mistake.outOfScope')}</h2>
        <Reason result={result} />
        {d && (
          <InLang lang={d.lang}>
            <RichText as="p" text={d.explanation} className="text-[15px] leading-relaxed" />
          </InLang>
        )}
      </Card>
      {d && <WhatToSay d={d} />}
      {tryAnother}
    </div>
  )
}
