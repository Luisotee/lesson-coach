import { useEffect, useRef, useState } from 'react'
import { transcribe } from '@/components/input/transcribe'
import type { ReviewLine } from '@/components/input/types'

export type Phase =
  | { kind: 'idle' }
  | { kind: 'reading' }
  /** A message key under `input.error.*` and its values, translated when shown (so it follows a language switch). */
  | { kind: 'failed'; error: string; params?: Record<string, unknown> }
  | { kind: 'review'; lines: ReviewLine[] }

/**
 * Runs one transcription: makes the image, sends it, and turns every outcome into a phase.
 * Failures become honest messages; nothing is retried behind the teacher's back. A pending
 * request is cancelled on reset and on unmount. `run` resolves to the phase it ended in, or
 * null when it was cancelled.
 */
export function useTranscription() {
  const [phase, setPhase] = useState<Phase>({ kind: 'idle' })
  const pending = useRef<AbortController | null>(null)
  useEffect(() => () => pending.current?.abort(), [])

  const run = async (makeImage: () => Promise<Blob>): Promise<Phase | null> => {
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
          error: result.error,
          params: { seconds: result.retryAfter ?? 60 },
        }
      } else if (result.status === 'unclear') {
        // `ai_unavailable`: the reader is down, not the image unreadable.
        next = {
          kind: 'failed',
          error: result.reason === 'ai_unavailable' ? 'unavailable' : 'unclear',
        }
      } else {
        next = { kind: 'review', lines: result.lines }
      }
    } catch (e) {
      if ((e as Error).name === 'AbortError') return null
      next = { kind: 'failed', error: 'image' }
    }
    if (pending.current !== controller) return null
    pending.current = null
    setPhase(next)
    return next
  }

  const reset = () => {
    pending.current?.abort()
    pending.current = null
    setPhase({ kind: 'idle' })
  }

  return { phase, run, reset }
}
