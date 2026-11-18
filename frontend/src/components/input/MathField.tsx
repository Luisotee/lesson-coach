import type { MathfieldElement } from 'mathlive'
import { useEffect, useImperativeHandle, useRef, useState, type Ref } from 'react'
import { useTranslation } from 'react-i18next'
import type { FieldValue } from '@/components/input/lines'
import { loadMathLive } from '@/components/input/mathlive'
import { cn } from '@/lib/utils'

export interface MathFieldHandle {
  focus(): void
}

export type { FieldValue } from '@/components/input/lines'

const box =
  'block min-h-12 w-full rounded-lg border border-input bg-white px-3 py-2 text-2xl text-navy focus-within:border-link focus-within:ring-[3px] focus-within:ring-navy'

/**
 * A MathLive field (typing `1/2` gives a stacked fraction; the virtual math keyboard opens on
 * touch). Reports LaTeX. MathLive loads lazily; if it can't load, a plain text field takes its
 * place and reports text. Always left to right.
 */
export function MathField({
  label,
  describedBy,
  invalid,
  onValue,
  ref,
}: {
  label: string
  describedBy?: string
  invalid?: boolean
  onValue: (value: FieldValue) => void
  ref?: Ref<MathFieldHandle>
}) {
  const { t, i18n } = useTranslation()
  const host = useRef<HTMLDivElement>(null)
  const field = useRef<MathfieldElement | null>(null)
  const fallback = useRef<HTMLInputElement>(null)
  const [state, setState] = useState<'loading' | 'ready' | 'failed'>('loading')
  // focus() asked for before the field exists (MathLive is still loading): honoured once it does.
  const wantFocus = useRef(false)
  const fieldClass = useRef<typeof MathfieldElement | null>(null)
  // The latest callback, so the field's listener never goes stale.
  const onValueRef = useRef(onValue)
  useEffect(() => {
    onValueRef.current = onValue
  })

  useEffect(() => {
    let cancelled = false
    let mf: MathfieldElement | null = null
    const onInput = () => mf && onValueRef.current({ latex: mf.value })
    loadMathLive()
      .then((MF) => {
        if (cancelled || !host.current) return
        MF.locale = i18n.language
        mf = new MF()
        mf.mathVirtualKeyboardPolicy = 'auto'
        mf.smartFence = true
        mf.setAttribute('data-testid', 'math-field')
        mf.className = 'block w-full outline-none'
        mf.addEventListener('input', onInput)
        host.current.appendChild(mf)
        field.current = mf
        fieldClass.current = MF
        setState('ready')
        if (wantFocus.current) {
          wantFocus.current = false
          mf.focus()
        }
      })
      .catch(() => !cancelled && setState('failed'))
    return () => {
      cancelled = true
      mf?.removeEventListener('input', onInput)
      mf?.remove()
      field.current = null
    }
    // The field is created once; its label is kept current below.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    const mf = field.current
    if (!mf) return
    mf.setAttribute('aria-label', label)
    if (describedBy) mf.setAttribute('aria-describedby', describedBy)
    else mf.removeAttribute('aria-describedby')
    if (invalid) mf.setAttribute('aria-invalid', 'true')
    else mf.removeAttribute('aria-invalid')
  }, [label, describedBy, invalid, state])

  // MathLive's strings (keyboard, menu) follow the UI language.
  useEffect(() => {
    if (fieldClass.current) fieldClass.current.locale = i18n.language
  }, [i18n.language, state])

  // The fallback field appears after a failed load: give it a focus asked for meanwhile.
  useEffect(() => {
    if (state === 'failed' && wantFocus.current) {
      wantFocus.current = false
      fallback.current?.focus()
    }
  }, [state])

  useImperativeHandle(ref, () => ({
    focus: () => {
      const el = field.current ?? fallback.current
      if (el) el.focus()
      else wantFocus.current = true
    },
  }))

  if (state === 'failed') {
    return (
      <div className="flex flex-col gap-1">
        <input
          ref={fallback}
          dir="ltr"
          aria-label={label}
          aria-describedby={describedBy}
          aria-invalid={invalid || undefined}
          className={cn(box, 'font-hand outline-none')}
          autoComplete="off"
          spellCheck={false}
          onChange={(e) => onValueRef.current({ text: e.target.value })}
        />
        <p className="text-sm text-muted-foreground">{t('input.type.fallback')}</p>
      </div>
    )
  }
  return (
    <div
      dir="ltr"
      className={cn(box, invalid && 'border-destructive')}
      aria-busy={state === 'loading'}
    >
      <div ref={host} />
      {state === 'loading' && (
        <span className="text-base text-muted-foreground" role="status">
          {t('input.type.loading')}
        </span>
      )}
    </div>
  )
}
