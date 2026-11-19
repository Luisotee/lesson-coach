import { Camera, Keyboard, PenLine } from 'lucide-react'
import { useEffect, useId, useImperativeHandle, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import type { MathFieldHandle } from '@/components/input/MathField'
import { toExpression, toLineIns } from '@/components/input/lines'
import { PhotoPanel } from '@/components/input/PhotoPanel'
import { TypeExpression, TypeLines } from '@/components/input/TypePanel'
import type {
  ConfirmedExpression,
  ConfirmedLines,
  InputMode,
  LineIn,
  MathIn,
  MathInputProps,
  ReviewLine,
} from '@/components/input/types'
import { WritePanel } from '@/components/input/WritePanel'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { cn } from '@/lib/utils'

const ICONS = { type: Keyboard, write: PenLine, photo: Camera }
const ALL: InputMode[] = ['type', 'write', 'photo']

type Value = ConfirmedExpression | ConfirmedLines | null

/**
 * Math from a teacher, three ways: type it, write it, or photograph it. Gives the page one
 * expression or a list of lines, in the API's shapes. Typed math is reported as it changes;
 * written and photographed math only once the teacher has confirmed what was read.
 * Each mode keeps its draft when the teacher switches; the value is always the active mode's.
 */
export function MathInput(props: MathInputProps) {
  const {
    label,
    description,
    error,
    confirmLabel,
    modes = ALL,
    defaultMode = 'type',
    className,
    ref,
  } = props
  const { t } = useTranslation()
  const id = useId()
  const offered = modes.includes('type') ? modes : (['type', ...modes] as InputMode[])
  const [mode, setMode] = useState<InputMode>(offered.includes(defaultMode) ? defaultMode : 'type')
  const values = useRef<Record<InputMode, Value>>({ type: null, write: null, photo: null })
  const typeField = useRef<MathFieldHandle>(null)
  const panels = useRef<Partial<Record<InputMode, HTMLDivElement | null>>>({})
  const triggers = useRef<Partial<Record<InputMode, HTMLButtonElement | null>>>({})
  const focusType = useRef(false)
  const single = props.shape === 'expression'

  // The latest onChange, so reports from panels never use a stale one.
  const onChange = useRef(props.onChange)
  useEffect(() => {
    onChange.current = props.onChange
  })
  const emit = (v: Value) => (onChange.current as (v: Value) => void)(v)

  const report = (from: InputMode, v: Value) => {
    values.current[from] = v
    if (from === mode) emit(v)
  }

  const select = (next: InputMode) => {
    setMode(next)
    emit(values.current[next])
  }

  useEffect(() => {
    if (mode === 'type' && focusType.current) {
      focusType.current = false
      typeField.current?.focus()
    }
  }, [mode])

  const typeInstead = () => {
    // The button is about to be hidden. MathLive gives up a focus() when the focused element
    // changes while it settles, so let go of the button first.
    if (document.activeElement instanceof HTMLElement) document.activeElement.blur()
    focusType.current = true
    select('type')
  }

  useImperativeHandle(ref, () => ({
    focus: () => {
      if (mode === 'type') return typeField.current?.focus()
      // The main control of what the panel shows now: Read, the crop box, the Use button, the set math…
      const main = panels.current[mode]?.querySelector<HTMLElement>('[data-main-control]')
      ;(main ?? triggers.current[mode])?.focus()
    },
    isUnconfirmed: () =>
      mode !== 'type' && !!panels.current[mode]?.querySelector('[data-unconfirmed]'),
  }))

  const fromLines = (m: InputMode) => (lines: ReviewLine[] | null) =>
    report(
      m,
      !lines
        ? null
        : single
          ? { mode: m, math: toExpression(lines[0]) }
          : { mode: m, lines: toLineIns(lines) },
    )

  const describedBy =
    [description && `${id}-desc`, error && `${id}-err`].filter(Boolean).join(' ') || undefined

  return (
    <fieldset
      className={cn('flex min-w-0 flex-col gap-2', className)}
      aria-describedby={describedBy}
    >
      <legend className="mb-1 text-base font-semibold">{label}</legend>
      {description && (
        <p id={`${id}-desc`} className="text-sm text-muted-foreground">
          {description}
        </p>
      )}
      <Tabs value={mode} onValueChange={(v) => select(v as InputMode)}>
        <TabsList aria-label={t('input.modes', { label })}>
          {offered.map((m) => {
            const Icon = ICONS[m]
            return (
              <TabsTrigger key={m} value={m} ref={(el) => void (triggers.current[m] = el)}>
                <Icon aria-hidden="true" />
                {t(`input.mode.${m}`)}
              </TabsTrigger>
            )
          })}
        </TabsList>
        {offered.map((m) => (
          <TabsContent
            key={m}
            value={m}
            forceMount
            hidden={mode !== m}
            ref={(el) => void (panels.current[m] = el)}
            tabIndex={m === 'type' ? -1 : 0}
            className="data-[state=inactive]:hidden"
          >
            {m === 'type' &&
              (single ? (
                <TypeExpression
                  ref={typeField}
                  label={label}
                  describedBy={describedBy}
                  invalid={!!error}
                  onChange={(math: MathIn | null) => report('type', math && { mode: 'type', math })}
                />
              ) : (
                <TypeLines
                  ref={typeField}
                  label={label}
                  describedBy={describedBy}
                  invalid={!!error}
                  onChange={(lines: LineIn[] | null) =>
                    report('type', lines && { mode: 'type', lines })
                  }
                />
              ))}
            {m === 'write' && (
              <WritePanel
                label={label}
                single={single}
                confirmLabel={confirmLabel}
                onLines={fromLines('write')}
                onTypeInstead={typeInstead}
              />
            )}
            {m === 'photo' && (
              <PhotoPanel
                label={label}
                single={single}
                confirmLabel={confirmLabel}
                onLines={fromLines('photo')}
                onTypeInstead={typeInstead}
              />
            )}
          </TabsContent>
        ))}
      </Tabs>
      {error && (
        <p id={`${id}-err`} className="text-sm font-semibold text-destructive">
          {error}
        </p>
      )}
    </fieldset>
  )
}
