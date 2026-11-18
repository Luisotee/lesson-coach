import { AlertTriangle, Check, Pencil, Plus, RotateCcw, Trash2 } from 'lucide-react'
import { useEffect, useId, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { EquationLine, Notebook } from '@/components/math'
import { isBlank, lineIssue } from '@/components/input/lines'
import { focusIfHere } from '@/components/input/focus'
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
 * The confirm step: what the model read, in the student's pencil, one line at a time. Lines it
 * wasn't sure of are marked; any line can be edited, removed or added. Nothing is used until
 * the teacher confirms, and an edit after confirming takes the confirmation back.
 */
export function TranscriptionReview({
  initial,
  single,
  image,
  retakeLabel,
  onConfirm,
  onUnconfirm,
  onRetake,
}: {
  initial: ReviewLine[]
  /** Exactly one line may be confirmed (one expression). */
  single: boolean
  /** The image that was read, shown for comparison. */
  image?: { url: string; alt: string }
  retakeLabel: string
  onConfirm: (lines: ReviewLine[]) => void
  onUnconfirm: () => void
  onRetake: () => void
}) {
  const { t } = useTranslation()
  const headingId = useId()
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

  const change = (next: Row[]) => {
    setRows(next)
    if (confirmed) {
      setConfirmed(false)
      onUnconfirm()
    }
  }
  const update = (id: number, patch: Partial<ReviewLine>) =>
    change(rows.map((r) => (r.id === id ? { ...r, ...patch } : r)))

  const filled = rows.filter((r) => !isBlank(r))
  const toCheck = rows.filter((r) => r.uncertain).length
  // The API's limits (backend/app/api/models.py), checked here so Confirm never sends a 422.
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
        <p role="status" className={cn('font-semibold', toCheck > 0 && 'text-navy')}>
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
        <ol className="flex min-w-0 flex-1 flex-col gap-3" aria-label={t('input.review.lines')}>
          {rows.map((row, i) => {
            const n = i + 1
            const isEditing = editing === row.id
            return (
              <li
                key={row.id}
                className={cn(
                  'flex flex-col gap-2 rounded-xl border border-line bg-white p-3',
                  row.uncertain && 'border-navy/40 bg-highlight/35',
                )}
                data-uncertain={row.uncertain || undefined}
              >
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-sm font-semibold">{t('input.review.lineN', { n })}</span>
                  {row.uncertain && (
                    <span className="inline-flex items-center gap-1 rounded-full bg-highlight px-2 py-0.5 text-sm font-semibold text-navy">
                      <AlertTriangle aria-hidden="true" className="size-4" />
                      {t('input.review.uncertain')}
                    </span>
                  )}
                  <span className="ms-auto flex gap-2">
                    <Button
                      id={`edit-${headingId}-${row.id}`}
                      type="button"
                      variant="outline"
                      className="min-h-11"
                      aria-expanded={isEditing}
                      aria-label={t(isEditing ? 'input.review.doneLine' : 'input.review.editLine', {
                        n,
                      })}
                      onClick={() => {
                        if (isEditing) update(row.id, { uncertain: false })
                        setEditing(isEditing ? null : row.id)
                        if (!isEditing) focusAfter.current = `left-${headingId}-${row.id}`
                      }}
                    >
                      {isEditing ? <Check aria-hidden="true" /> : <Pencil aria-hidden="true" />}
                      <span aria-hidden="true">
                        {t(isEditing ? 'input.review.done' : 'input.review.edit')}
                      </span>
                    </Button>
                    <Button
                      type="button"
                      variant="outline"
                      className="min-h-11"
                      aria-label={t('input.review.removeLine', { n })}
                      onClick={() => {
                        const next = rows.filter((r) => r.id !== row.id)
                        change(next)
                        if (editing === row.id) setEditing(null)
                        focusAfter.current = next.length
                          ? `edit-${headingId}-${next[Math.max(0, i - 1)].id}`
                          : `add-${headingId}`
                      }}
                    >
                      <Trash2 aria-hidden="true" />
                    </Button>
                  </span>
                </div>
                {isBlank(row) ? (
                  <p className="text-muted-foreground">{t('input.review.blank')}</p>
                ) : (
                  <Notebook
                    label={t('input.review.lineN', { n })}
                    pen="pencil"
                    className="px-3 py-2 text-2xl sm:text-2xl"
                  >
                    <EquationLine left={row.left} right={row.right} op={row.op} />
                  </Notebook>
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
                        id={`left-${headingId}-${row.id}`}
                        className={field}
                        value={row.left}
                        maxLength={LIMITS.text}
                        autoComplete="off"
                        spellCheck={false}
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
                        onChange={(e) => update(row.id, { op: e.target.value })}
                      />
                    </label>
                  </div>
                )}
              </li>
            )
          })}
        </ol>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        {rows.length < LIMITS.lines && (
          <Button
            id={`add-${headingId}`}
            type="button"
            variant="outline"
            className="min-h-11"
            onClick={() => {
              const id = nextId.current++
              change([...rows, { id, left: '', right: '', op: '', uncertain: false }])
              setEditing(id)
              focusAfter.current = `left-${headingId}-${id}`
            }}
          >
            <Plus aria-hidden="true" />
            {t('input.review.addLine')}
          </Button>
        )}
        <Button type="button" variant="outline" className="min-h-11" onClick={onRetake}>
          <RotateCcw aria-hidden="true" />
          {retakeLabel}
        </Button>
      </div>

      {blocked && (
        <p className="text-sm font-semibold">
          {t(`input.review.blocked.${blocked}`, { max: LIMITS.lines, chars: LIMITS.text })}
        </p>
      )}
      <div className="flex flex-wrap items-center gap-3">
        <Button
          type="button"
          className="min-h-11 px-5 aria-disabled:opacity-50"
          aria-disabled={!!blocked || confirmed || undefined}
          onClick={() => {
            if (blocked || confirmed) return
            setEditing(null)
            setConfirmed(true)
            onConfirm(filled)
          }}
        >
          <Check aria-hidden="true" />
          {t('input.review.confirm')}
        </Button>
        <p role="status" className="font-semibold text-green-text">
          {confirmed ? t('input.review.confirmed') : ''}
        </p>
      </div>
    </section>
  )
}
