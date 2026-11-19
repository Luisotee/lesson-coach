import { Keyboard, Loader2 } from 'lucide-react'
import { useEffect, useRef } from 'react'
import { useTranslation } from 'react-i18next'
import { focusIfHere } from '@/components/input/focus'
import type { Phase } from '@/components/input/useTranscription'
import { Button } from '@/components/ui/button'

/** "Type it instead": always offered next to the drawing board and the camera. */
export function TypeInstead({
  onClick,
  variant = 'outline',
}: {
  onClick: () => void
  variant?: 'outline' | 'ghost'
}) {
  const { t } = useTranslation()
  return (
    <Button type="button" variant={variant} className="min-h-11" onClick={onClick}>
      <Keyboard aria-hidden="true" />
      {t('input.typeInstead')}
    </Button>
  )
}

/** The reading and failed states of a transcription, announced to screen readers. */
export function ReadingStatus({ phase, readingLabel }: { phase: Phase; readingLabel: string }) {
  const { t } = useTranslation()
  const alert = useRef<HTMLParagraphElement>(null)
  // Each failure is a new state object, kept stable across renders: focus it once when it
  // appears, not again on a re-render or a language switch.
  const failure = phase.kind === 'failed' ? phase : null
  useEffect(() => {
    if (failure) focusIfHere(alert.current)
  }, [failure])
  return (
    <>
      <p role="status" className="flex items-center gap-2 empty:hidden">
        {phase.kind === 'reading' && (
          <>
            <Loader2 aria-hidden="true" className="size-5 motion-safe:animate-spin" />
            {readingLabel}
          </>
        )}
      </p>
      {phase.kind === 'failed' && (
        <p
          ref={alert}
          role="alert"
          tabIndex={-1}
          className="rounded-xl border border-destructive/40 bg-white p-3 font-semibold text-destructive outline-none"
        >
          {t(`input.error.${phase.error}`, { ...phase.params })}
        </p>
      )}
    </>
  )
}
