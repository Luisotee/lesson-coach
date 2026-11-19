import { AlertTriangle, Check, CircleCheck, Pencil, Plus, RotateCcw, Trash2 } from 'lucide-react'
import { useEffect, useId, useRef, useState, type KeyboardEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { EquationLine, Notebook } from '@/components/math'
import { isBlank, lineIssue } from '@/components/input/lines'
import { focusIfHere } from '@/components/input/focus'
import { TypeInstead } from '@/components/input/Reading'
import { LIMITS, type ReviewLine } from '@/components/input/types'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import { parseLine } from '@/math/parse'

interface Row extends ReviewLine {
  id: number
}

const readable = (l: ReviewLine) => {
  const p = parseLine(l)
  return p.left.ok && (p.right?.ok ?? true) && (p.op?.ok ?? true)
}

const field =
  'min-h-11 w-full rounded-lg border border-input bg-white px-3 font-hand text-xl text-navy outline-none focus:border-link focus:ring-[3px] focus:ring-navy'

/**
 * What the model read, checked by the teacher before it is used, then shown as the field's value.
 *
 * Check: each line in the student's pencil; lines it wasn't sure of are marked; any line can be
 * edited, removed or added. One primary button uses the lines ("Use this problem"); drawing
 * again or typing instead sit beside it as quieter ways out.
 *
 * Set: the confirmed math in ink, marked as set, with Change. The field holds a value exactly
 * while this view shows: Change takes it back (`onUnconfirm`) until the lines are used again,
 * so nothing unconfirmed is ever checked.
 */
export function TranscriptionReview({
  initial,
  single,
  label,
  source,
  image,
  confirmLabel,
  retakeLabel,
  onConfirm,
  onUnconfirm,
  onRetake,
  onTypeInstead,
}: {
  initial: ReviewLine[]
  /** Exactly one line may be confirmed (one expression). */
  single: boolean
  /** The field's label, e.g. "The problem": names the Change button. */
  label: string
  /** Where the lines came from, for the "set" caption. */
  source: 'write' | 'photo'
  /** The image that was read, shown for comparison. */
  image?: { url: string; alt: string }
  /** The primary button, worded for the field ("Use this problem"). */
  confirmLabel?: string
  retakeLabel: string
  onConfirm: (lines: ReviewLine[]) => void
  onUnconfirm: () => void
  onRetake: () => void
  onTypeInstead: () => void
}) {
  const { t } = useTranslation()
  const uid = useId()
  const headingId = `heading-${uid}`
  const setId = `set-${uid}`
  const heading = useRef<HTMLHeadingElement>(null)
  const nextId = useRef(initial.length)
  const [rows, setRows] = useState<Row[]>(() => initial.map((l, id) => ({ ...l, id })))
  const [editing, setEditing] = useState<number | null>(null)
  const [confirmed, setConfirmed] = useState(false)
  const focusAfter = useRef<string | null>(null)

  useEffect(() => focusIfHere(heading.current), [])
  useEffect(() => {
    if (!focusAfter.current) return
    document.getElementById(focusAfter.current)?.focus()
    focusAfter.current = null
  })

  const update = (id: number, patch: Partial<ReviewLine>) =>
    setRows(rows.map((r) => (r.id === id ? { ...r, ...patch } : r)))

  const finishEditing = (id: number) => {
    update(id, { uncertain: false })
    setEditing(null)
  }

  const filled = rows.filter((r) => !isBlank(r))
  const toCheck = rows.filter((r) => r.uncertain).length
  // The API's limits (backend/app/api/models.py), checked here so using the lines never sends a 422.
  const blocked =
    filled.length === 0
      ? 'none'
      : single && filled.length > 1
        ? 'oneLine'
        : filled.length > LIMITS.lines
          ? 'tooMany'
          : filled.some(lineIssue)
            ? 'tooLong'
            : null

  if (confirmed) {
    return (
      <div
        id={setId}
        role="group"
        aria-labelledby={`${setId}-caption`}
        tabIndex={-1}
        data-main-control
        data-testid="confirmed-math"
        className="flex flex-col gap-2 rounded-xl border border-input bg-white p-3 outline-none focus-visible:ring-[3px] focus-visible:ring-ring"
      >
        <div className="flex flex-wrap items-center gap-2">
          <p
            id={`${setId}-caption`}
            className="flex items-center gap-1.5 text-sm font-semibold text-green-text"
          >
            <CircleCheck aria-hidden="true" className="size-5 text-green" />
            {t(source === 'photo' ? 'input.set.fromPhoto' : 'input.set.fromWrite')}
          </p>
          <Button
            type="button"
            variant="outline"
            className="ms-auto min-h-11"
            aria-label={t('input.set.changeLabel', { label })}
            onClick={() => {
              setConfirmed(false)
              onUnconfirm()
              focusAfter.current = headingId
            }}
          >
            <Pencil aria-hidden="true" />
            {t('input.set.change')}
          </Button>
        </div>
        <Notebook
          label={label}
          pen="ink"
          numbered={!single}
          className="px-3 py-2 text-2xl sm:text-2xl"
        >
          {filled.map((r) => (
            <EquationLine key={r.id} left={r.left} right={r.right} op={r.op} />
          ))}
        </Notebook>
      </div>
    )
  }

  const canRemove = !single || rows.length > 1
  const canAdd = single ? rows.length === 0 : rows.length < LIMITS.lines

  return (
    <section aria-labelledby={headingId} className="flex flex-col gap-4">
      <div className="flex flex-col gap-1">
        <h3
          id={headingId}
          ref={heading}
          tabIndex={-1}
          data-main-control
          className="text-lg font-semibold outline-none"
        >
          {t('input.review.heading')}
        </h3>
        <p className="text-muted-foreground">{t('input.review.intro')}</p>
        <p role="status" className="font-semibold text-navy empty:hidden">
          {toCheck > 0 ? t('input.review.toCheck', { count: toCheck }) : ''}
        </p>
      </div>

      <div className="flex flex-col gap-4 lg:flex-row lg:items-start">
        {image && (
          <img
            src={image.url}
            alt={image.alt}
            className="max-h-64 w-auto max-w-full self-start rounded-xl border border-line object-contain lg:max-w-[40%]"
          />
        )}
        <div className="flex min-w-0 flex-1 flex-col gap-2">
          <ol className="flex flex-col gap-2" aria-label={t('input.review.lines')}>
            {rows.map((row, i) => {
              const n = i + 1
              const isEditing = editing === row.id
              const onEnter = (e: KeyboardEvent<HTMLInputElement>) => {
                // Enter ends the edit; inside a page's <form> it would otherwise submit it.
                if (e.key !== 'Enter') return
                e.preventDefault()
                finishEditing(row.id)
                focusAfter.current = `edit-${uid}-${row.id}`
              }
              return (
                <li
                  key={row.id}
                  className={cn(
                    'flex flex-col gap-2 rounded-xl border border-line bg-white p-2',
                    row.uncertain && 'border-navy/40 bg-highlight/35',
                  )}
                  data-uncertain={row.uncertain || undefined}
                >
                  <div className="flex flex-wrap items-center gap-2">
                    {!single && (
                      <span
                        aria-hidden="true"
                        className="w-6 text-center text-sm font-semibold text-muted-foreground"
                      >
                        {n}
                      </span>
                    )}
                    <div className="min-w-48 flex-1">
                      {isBlank(row) ? (
                        <p className="px-3 py-2 text-muted-foreground">{t('input.review.blank')}</p>
                      ) : (
                        <Notebook
                          label={t('input.review.lineN', { n })}
                          pen="pencil"
                          className="px-3 py-2 text-2xl sm:text-2xl"
                        >
                          <EquationLine left={row.left} right={row.right} op={row.op} />
                        </Notebook>
                      )}
                    </div>
                    <span className="ms-auto flex gap-1">
                      <Button
                        id={`edit-${uid}-${row.id}`}
                        type="button"
                        variant="ghost"
                        className="min-h-11 min-w-11"
                        aria-expanded={isEditing}
                        aria-label={t(
                          isEditing ? 'input.review.doneLine' : 'input.review.editLine',
                          { n },
                        )}
                        onClick={() => {
                          if (isEditing) return finishEditing(row.id)
                          setEditing(row.id)
                          focusAfter.current = `left-${uid}-${row.id}`
                        }}
                      >
                        {isEditing ? <Check aria-hidden="true" /> : <Pencil aria-hidden="true" />}
                        <span aria-hidden="true">
                          {t(isEditing ? 'input.review.done' : 'input.review.edit')}
                        </span>
                      </Button>
                      {canRemove && (
                        <Button
                          type="button"
                          variant="ghost"
                          className="min-h-11 min-w-11"
                          aria-label={t('input.review.removeLine', { n })}
                          title={t('input.review.removeLine', { n })}
                          onClick={() => {
                            const next = rows.filter((r) => r.id !== row.id)
                            setRows(next)
                            if (editing === row.id) setEditing(null)
                            focusAfter.current = next.length
                              ? `edit-${uid}-${next[Math.max(0, i - 1)].id}`
                              : headingId
                          }}
                        >
                          <Trash2 aria-hidden="true" />
                        </Button>
                      )}
                    </span>
                  </div>
                  {row.uncertain && (
                    <span className="inline-flex items-center gap-1 self-start rounded-full bg-highlight px-2 py-0.5 text-sm font-semibold text-navy">
                      <AlertTriangle aria-hidden="true" className="size-4" />
                      {t('input.review.uncertain')}
                    </span>
                  )}
                  {!isBlank(row) && !readable(row) && (
                    <p className="text-sm text-muted-foreground">{t('input.review.unreadable')}</p>
                  )}
                  {isEditing && (
                    <div
                      dir="ltr"
                      className="grid gap-2 sm:grid-cols-[1fr_auto_1fr_8rem] sm:items-end"
                    >
                      <label className="flex flex-col gap-1 text-sm font-semibold">
                        <span dir="auto">{t('input.review.left')}</span>
                        <input
                          id={`left-${uid}-${row.id}`}
                          className={field}
                          value={row.left}
                          maxLength={LIMITS.text}
                          autoComplete="off"
                          spellCheck={false}
                          onKeyDown={onEnter}
                          onChange={(e) => update(row.id, { left: e.target.value })}
                        />
                      </label>
                      <span aria-hidden="true" className="hidden pb-2 font-hand text-2xl sm:block">
                        =
                      </span>
                      <label className="flex flex-col gap-1 text-sm font-semibold">
                        <span dir="auto">{t('input.review.right')}</span>
                        <input
                          className={field}
                          value={row.right}
                          maxLength={LIMITS.text}
                          autoComplete="off"
                          spellCheck={false}
                          onKeyDown={onEnter}
                          onChange={(e) => update(row.id, { right: e.target.value })}
                        />
                      </label>
                      <label className="flex flex-col gap-1 text-sm font-semibold">
                        <span dir="auto">{t('input.review.op')}</span>
                        <input
                          className={field}
                          value={row.op}
                          maxLength={LIMITS.op}
                          autoComplete="off"
                          spellCheck={false}
                          onKeyDown={onEnter}
                          onChange={(e) => update(row.id, { op: e.target.value })}
                        />
                      </label>
                    </div>
                  )}
                </li>
              )
            })}
          </ol>
          {canAdd && (
            <Button
              type="button"
              variant="ghost"
              className="min-h-11 self-start"
              onClick={() => {
                const id = nextId.current++
                setRows([...rows, { id, left: '', right: '', op: '', uncertain: false }])
                setEditing(id)
                focusAfter.current = `left-${uid}-${id}`
              }}
            >
              <Plus aria-hidden="true" />
              {t('input.review.addLine')}
            </Button>
          )}
        </div>
      </div>

      <div className="flex flex-col gap-2">
        {blocked && (
          <p id={`${uid}-blocked`} className="text-sm font-semibold">
            {t(`input.review.blocked.${blocked}`, { max: LIMITS.lines, chars: LIMITS.text })}
          </p>
        )}
        <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
          <Button
            type="button"
            className="min-h-12 px-6 text-base aria-disabled:opacity-50"
            aria-disabled={!!blocked || undefined}
            aria-describedby={blocked ? `${uid}-blocked` : undefined}
            onClick={() => {
              if (blocked) return
              setEditing(null)
              setConfirmed(true)
              focusAfter.current = setId
              onConfirm(filled)
            }}
          >
            <Check aria-hidden="true" />
            {confirmLabel ?? t(single ? 'input.review.useOne' : 'input.review.useLines')}
          </Button>
          <div className="flex flex-wrap items-center gap-1">
            <span className="text-sm text-muted-foreground">{t('input.review.notRight')}</span>
            <Button type="button" variant="ghost" className="min-h-11" onClick={onRetake}>
              <RotateCcw aria-hidden="true" />
              {retakeLabel}
            </Button>
            <TypeInstead variant="ghost" onClick={onTypeInstead} />
          </div>
        </div>
      </div>
    </section>
  )
}
