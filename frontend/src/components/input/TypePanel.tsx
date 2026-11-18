import { Plus, X } from 'lucide-react'
import { useId, useImperativeHandle, useRef, useState, type Ref } from 'react'
import { useTranslation } from 'react-i18next'
import { MathField, type FieldValue, type MathFieldHandle } from '@/components/input/MathField'
import { latexValue, textValue } from '@/components/input/lines'
import { LIMITS, type LineIn, type MathIn } from '@/components/input/types'
import { Button } from '@/components/ui/button'

const toMath = (v: FieldValue): MathIn | null =>
  'latex' in v ? latexValue(v.latex) : textValue(v.text)

const tooLong = (v: FieldValue | undefined) =>
  !!v && ('latex' in v ? v.latex.trim().length > LIMITS.latex : v.text.trim().length > LIMITS.text)

/** One typed expression. Reports `{latex}` (or `{text}` from the fallback), or null. */
export function TypeExpression({
  label,
  describedBy,
  invalid,
  onChange,
  ref,
}: {
  label: string
  describedBy?: string
  invalid?: boolean
  onChange: (v: MathIn | null) => void
  ref?: Ref<MathFieldHandle>
}) {
  const { t } = useTranslation()
  const errorId = useId()
  const [value, setValue] = useState<FieldValue>()
  const long = tooLong(value)
  return (
    <div className="flex flex-col gap-2">
      <MathField
        ref={ref}
        label={label}
        describedBy={[describedBy, long && errorId].filter(Boolean).join(' ') || undefined}
        invalid={invalid || long}
        onValue={(v) => {
          setValue(v)
          onChange(toMath(v))
        }}
      />
      {long && (
        <p id={errorId} className="text-sm font-semibold text-destructive">
          {t('input.type.tooLong')}
        </p>
      )}
    </div>
  )
}

/** A fallback text line as a step: split at its `=` when it has exactly one. */
function toLine(m: MathIn): LineIn {
  if ('latex' in m) return m
  const sides = m.text.split('=')
  return sides.length === 2 ? { left: sides[0].trim(), right: sides[1].trim() } : { left: m.text }
}

interface Row {
  id: number
  value?: FieldValue
}

/** Typed lines of working, one field per line. Reports `{latex}` per line, or null. */
export function TypeLines({
  label,
  describedBy,
  invalid,
  onChange,
  ref,
}: {
  label: string
  describedBy?: string
  invalid?: boolean
  onChange: (v: LineIn[] | null) => void
  ref?: Ref<MathFieldHandle>
}) {
  const { t } = useTranslation()
  const errorId = useId()
  const [rows, setRows] = useState<Row[]>([{ id: 0 }])
  const nextId = useRef(1)
  const fields = useRef(new Map<number, MathFieldHandle>())
  const [focusId, setFocusId] = useState<number | null>(null)

  useImperativeHandle(ref, () => ({ focus: () => fields.current.get(rows[0].id)?.focus() }))

  const report = (next: Row[]) => {
    setRows(next)
    if (next.some((r) => tooLong(r.value))) return onChange(null)
    const lines = next.map((r) => r.value && toMath(r.value)).filter((m): m is MathIn => !!m)
    onChange(lines.length ? lines.map(toLine) : null)
  }

  const long = rows.some((r) => tooLong(r.value))
  return (
    <div className="flex flex-col gap-2">
      <ol className="flex flex-col gap-2">
        {rows.map((row, i) => (
          <li key={row.id} className="flex items-start gap-2">
            <div className="min-w-0 flex-1">
              <MathField
                ref={(h) => {
                  if (h) {
                    fields.current.set(row.id, h)
                    if (focusId === row.id) {
                      h.focus()
                      setFocusId(null)
                    }
                  } else fields.current.delete(row.id)
                }}
                label={t('input.type.lineLabel', { label, n: i + 1 })}
                describedBy={[describedBy, long && errorId].filter(Boolean).join(' ') || undefined}
                invalid={invalid || tooLong(row.value)}
                onValue={(v) => report(rows.map((r) => (r.id === row.id ? { ...r, value: v } : r)))}
              />
            </div>
            {rows.length > 1 && (
              <Button
                type="button"
                variant="outline"
                className="size-12"
                aria-label={t('input.type.removeLine', { n: i + 1 })}
                onClick={() => {
                  const next = rows.filter((r) => r.id !== row.id)
                  report(next)
                  fields.current.get(next[Math.max(0, i - 1)].id)?.focus()
                }}
              >
                <X aria-hidden="true" />
              </Button>
            )}
          </li>
        ))}
      </ol>
      {long && (
        <p id={errorId} className="text-sm font-semibold text-destructive">
          {t('input.type.tooLong')}
        </p>
      )}
      {rows.length < LIMITS.lines && (
        <Button
          type="button"
          variant="outline"
          className="min-h-11 self-start"
          onClick={() => {
            const id = nextId.current++
            setRows([...rows, { id }])
            setFocusId(id)
          }}
        >
          <Plus aria-hidden="true" />
          {t('input.type.addLine')}
        </Button>
      )}
    </div>
  )
}
