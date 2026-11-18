import { Lightbulb, RotateCcw } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router'
import type { PracticeItem } from '@/api/types'
import { RichText } from '@/components/RichText'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

/**
 * The four hint rungs (goal, information, computation, answer), opened one at a time.
 * Nothing is counted or kept: leaving the problem forgets which hints were open.
 */
export function HintLadder({ item, topic }: { item: PracticeItem; topic: string }) {
  const { t } = useTranslation()
  const [shown, setShown] = useState(0)
  const newest = useRef<HTMLLIElement>(null)
  const next = useRef<HTMLButtonElement>(null)
  // Where focus goes after the hints change: a hint just opened is read next; after Start over
  // (whose button disappears) focus goes to Show next hint.
  const focusAfter = useRef<'newest' | 'next' | null>(null)

  useEffect(() => {
    const to = focusAfter.current
    focusAfter.current = null
    if (to === 'newest') newest.current?.focus()
    if (to === 'next') next.current?.focus()
  }, [shown])

  const total = item.hints.length
  const done = shown >= total
  return (
    <aside
      aria-labelledby="hints-heading"
      className="flex flex-col gap-4 rounded-[20px] border border-line bg-white p-5"
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 id="hints-heading" className="text-lg font-semibold">
          {t('practice.hintsHeading')}
        </h2>
        {shown > 0 && (
          <Button
            variant="ghost"
            className="min-h-11"
            onClick={() => {
              focusAfter.current = 'next'
              setShown(0)
            }}
          >
            <RotateCcw aria-hidden="true" />
            {t('practice.startOver')}
          </Button>
        )}
      </div>
      <ol className="flex flex-col gap-2">
        {item.hints.map((h, i) => {
          const on = i < shown
          return (
            <li
              key={h.rung}
              ref={on && i === shown - 1 ? newest : undefined}
              tabIndex={on && i === shown - 1 ? -1 : undefined}
              className={cn(
                'flex gap-3 rounded-xl border p-3',
                on
                  ? 'border-line bg-white'
                  : i === shown
                    ? 'border-paleblue bg-[#eef1f4]'
                    : 'border-[#e9ecf0] bg-[#eef1f4]',
              )}
            >
              <span
                aria-hidden="true"
                className={cn(
                  'flex size-7 flex-none items-center justify-center rounded-full text-sm font-bold',
                  on ? 'bg-navy text-white' : 'bg-line text-muted-foreground',
                )}
              >
                {i + 1}
              </span>
              <div className="flex flex-col gap-1">
                <span
                  className={cn(
                    'text-sm font-semibold',
                    on ? 'text-link-ink' : 'text-muted-foreground',
                  )}
                >
                  {t(`practice.rung.${h.rung}`)}
                  {!on && <span className="sr-only"> {t('practice.hidden')}</span>}
                </span>
                {on && <RichText as="p" text={h.text} className="text-[15px] leading-relaxed" />}
              </div>
            </li>
          )
        })}
      </ol>
      {!done ? (
        <Button
          ref={next}
          className="min-h-11 self-start"
          onClick={() => {
            focusAfter.current = 'newest'
            setShown(shown + 1)
          }}
        >
          <Lightbulb aria-hidden="true" />
          {shown === total - 1 ? t('practice.showAnswer') : t('practice.showNextHint')}
        </Button>
      ) : (
        <p className="rounded-xl bg-[#ecfdf5] p-3 text-[15px] text-green-text">
          {t('practice.doneNote')}{' '}
          <Link to={`/topics/${topic}#example`} className="font-semibold text-green-text underline">
            {t('practice.openExample')}
          </Link>
        </p>
      )}
    </aside>
  )
}
