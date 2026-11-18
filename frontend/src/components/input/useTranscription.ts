import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { transcribe } from '@/components/input/transcribe'
import type { ReviewLine } from '@/components/input/types'

export type Phase =
  | { kind: 'idle' }
  | { kind: 'reading' }
  | { kind: 'failed'; message: string }
  | { kind: 'review'; lines: ReviewLine[] }

/**
 * Runs one transcription: makes the image, sends it, and turns every outcome into a phase.
 * Failures become honest messages; nothing is retried behind the teacher's back. A pending
 * request is cancelled on reset and on unmount.
 */
export function useTranscription() {
  const { t } = useTranslation()
  const [phase, setPhase] = useState<Phase>({ kind: 'idle' })
  const pending = useRef<AbortController | null>(null)
  useEffect(() => () => pending.current?.abort(), [])

  const run = async (makeImage: () => Promise<Blob>) => {
    pending.current?.abort()
    const controller = new AbortController()
    pending.current = controller
    setPhase({ kind: 'reading' })
    let next: Phase
    try {
      const result = await transcribe(await makeImage(), { signal: controller.signal })
      if (!result.ok) {
        next = {
          kind: 'failed',
          message: t(`input.error.${result.error}`, { seconds: result.retryAfter ?? 60 }),
        }
      } else if (result.status === 'unclear') {
        // `ai_unavailable`: the reader is down, not the image unreadable.
        next = {
          kind: 'failed',
          message: t(
            result.reason === 'ai_unavailable' ? 'input.error.unavailable' : 'input.error.unclear',
          ),
        }
      } else {
        next = { kind: 'review', lines: result.lines }
      }
    } catch (e) {
      if ((e as Error).name === 'AbortError') return
      next = { kind: 'failed', message: t('input.error.image') }
    }
    if (pending.current === controller) {
      pending.current = null
      setPhase(next)
    }
  }

  const reset = () => {
    pending.current?.abort()
    pending.current = null
    setPhase({ kind: 'idle' })
  }

  return { phase, run, reset }
}
