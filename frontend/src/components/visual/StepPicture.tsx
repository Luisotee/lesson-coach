import { motion, useReducedMotion } from 'motion/react'
import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { MathExpr } from '@/components/math/MathExpr'
import { RichText } from '@/components/RichText'
import { cn } from '@/lib/utils'
import { MAX_TILES, pictureFor } from '@/components/visual/picture'
import { variableTermOf, type Term } from '@/math/terms'
import type { MathNode, Step } from '@/math/types'

/**
 * The "Picture" explanation of one step, drawn from the step's own math so it always matches
 * the verified line: a balance scale for an equation, a bar model for fractions, counters for
 * small whole numbers. The pack's `visual` sentence is the caption. When the math has no
 * picture we can draw honestly, only the caption is shown. Nothing is computed.
 */

function useEntrance(i: number) {
  const reduce = useReducedMotion()
  return reduce
    ? {}
    : {
        initial: { opacity: 0, y: -10, scale: 0.9 },
        animate: { opacity: 1, y: 0, scale: 1 },
        transition: { delay: 0.05 * i, type: 'spring' as const, stiffness: 300, damping: 22 },
      }
}

function Tile({ i, className, children }: { i: number; className: string; children: ReactNode }) {
  const entrance = useEntrance(i)
  return (
    <motion.span
      {...entrance}
      className={cn(
        'inline-flex h-9 min-w-9 items-center justify-center rounded-md px-1.5 font-hand text-lg',
        className,
      )}
    >
      {children}
    </motion.span>
  )
}

function SideTiles({ terms }: { terms: Term[] }) {
  let i = 0
  return (
    <span className="flex flex-wrap items-end justify-center gap-1">
      {terms.flatMap((term, k) => {
        const v = variableTermOf(term.node)
        if (v && term.sign === 1 && v.coef <= MAX_TILES) {
          return Array.from({ length: v.coef }, (_, j) => (
            <Tile key={`${k}-${j}`} i={i++} className="bg-navy text-white">
              <i>{v.name}</i>
            </Tile>
          ))
        }
        const node: MathNode = term.sign === -1 ? { type: 'neg', arg: term.node } : term.node
        return [
          <Tile key={k} i={i++} className="border border-line-strong bg-white text-navy">
            <MathExpr node={node} />
          </Tile>,
        ]
      })}
    </span>
  )
}

function Balance({ left, right }: { left: Term[]; right: Term[] }) {
  const reduce = useReducedMotion()
  return (
    <div className="flex flex-col items-center" aria-hidden="true" data-picture="balance">
      <motion.div
        className="flex w-full max-w-sm origin-bottom items-end justify-between gap-3"
        initial={reduce ? false : { rotate: -6 }}
        animate={{ rotate: 0 }}
        transition={{ type: 'spring', stiffness: 80, damping: 12 }}
        dir="ltr"
      >
        <div className="flex min-h-12 flex-1 flex-col items-center gap-1">
          <SideTiles terms={left} />
          <span className="h-1.5 w-full rounded-full bg-navy/80" />
        </div>
        <div className="flex min-h-12 flex-1 flex-col items-center gap-1">
          <SideTiles terms={right} />
          <span className="h-1.5 w-full rounded-full bg-navy/80" />
        </div>
      </motion.div>
      <div className="h-1 w-full max-w-sm rounded bg-navy" />
      <svg width="40" height="34" viewBox="0 0 40 34" className="text-navy">
        <path d="M20 0 L36 34 H4 Z" fill="currentColor" />
      </svg>
    </div>
  )
}

function Bars({ terms }: { terms: { sign: 1 | -1; num: number; den: number }[] }) {
  return (
    <div
      className="flex flex-wrap items-center justify-center gap-3"
      aria-hidden="true"
      data-picture="bars"
      dir="ltr"
    >
      {terms.map((term, k) => {
        const bars = Math.max(1, Math.ceil(term.num / term.den))
        return (
          <span key={k} className="flex items-center gap-3">
            {k > 0 && <span className="font-hand text-2xl">{term.sign === 1 ? '+' : '−'}</span>}
            <span className="flex flex-col items-center gap-1">
              {Array.from({ length: bars }, (_, b) => (
                <span
                  key={b}
                  className="flex h-7 w-36 overflow-hidden rounded border-2 border-navy"
                >
                  {Array.from({ length: term.den }, (_, s) => {
                    const filled = b * term.den + s < term.num
                    return (
                      <BarCell
                        key={s}
                        i={b * term.den + s}
                        filled={filled}
                        last={s === term.den - 1}
                      />
                    )
                  })}
                </span>
              ))}
              <MathExpr expr={`${term.num}/${term.den}`} className="text-lg" />
            </span>
          </span>
        )
      })}
    </div>
  )
}

function BarCell({ i, filled, last }: { i: number; filled: boolean; last: boolean }) {
  const reduce = useReducedMotion()
  return (
    <span className={cn('relative flex-1', !last && 'border-e-2 border-navy/60')}>
      {filled && (
        <motion.span
          className="absolute inset-0 bg-highlight"
          initial={reduce ? false : { scaleY: 0 }}
          animate={{ scaleY: 1 }}
          transition={{ delay: 0.04 * i }}
        />
      )}
    </span>
  )
}

function Counters({ terms }: { terms: { sign: 1 | -1; n: number }[] }) {
  let i = 0
  return (
    <div
      className="flex flex-wrap items-center justify-center gap-3"
      aria-hidden="true"
      data-picture="counters"
      dir="ltr"
    >
      {terms.map((term, k) => (
        <span key={k} className="flex items-center gap-3">
          {k > 0 && <span className="font-hand text-2xl">{term.sign === 1 ? '+' : '−'}</span>}
          <span className="flex max-w-40 flex-wrap justify-center gap-1 rounded-lg border border-dashed border-line-strong p-1.5">
            {Array.from({ length: Math.abs(term.n) }, () => (
              <Tile
                key={i}
                i={i++}
                className={cn(
                  'size-8 min-w-8 rounded-full p-0 font-sans text-base font-bold',
                  term.n > 0 ? 'bg-highlight text-navy' : 'bg-navy text-white',
                )}
              >
                {term.n > 0 ? '+' : '−'}
              </Tile>
            ))}
            {term.n === 0 && <span className="px-2 font-hand text-lg">0</span>}
          </span>
        </span>
      ))}
    </div>
  )
}

export function StepPicture({
  step,
  caption,
}: {
  step: Pick<Step, 'left' | 'right'>
  caption: string
}) {
  const { t } = useTranslation()
  const picture = pictureFor(step)
  return (
    <figure className="flex flex-col gap-4">
      {picture?.kind === 'balance' && <Balance left={picture.left} right={picture.right} />}
      {picture?.kind === 'bars' && <Bars terms={picture.terms} />}
      {picture?.kind === 'counters' && <Counters terms={picture.terms} />}
      <figcaption className="text-[15px] leading-relaxed">
        {picture?.kind === 'counters' && (
          <span className="mb-1 block text-sm text-muted-foreground">{t('topic.countersKey')}</span>
        )}
        <RichText text={caption} />
      </figcaption>
    </figure>
  )
}
