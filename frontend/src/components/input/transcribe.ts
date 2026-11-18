import type { ReviewLine } from '@/components/input/types'

/** One line as `/api/transcribe` returns it. */
interface ApiLine {
  left: string
  right: string
  op: string
  confidence: number
  uncertain: boolean
}

export type TranscribeError = 'too_large' | 'rate_limited' | 'unavailable' | 'bad_image'

export type TranscribeResult =
  | { ok: true; status: 'ok'; lines: ReviewLine[] }
  | { ok: true; status: 'unclear'; reason: string | null }
  | { ok: false; error: TranscribeError; retryAfter?: number }

/** Below this the line is marked for a check, whatever the server says. Same as the API's. */
export const UNCERTAIN_BELOW = 0.7

function isApiLine(v: unknown): v is ApiLine {
  if (typeof v !== 'object' || v === null) return false
  const l = v as Record<string, unknown>
  return typeof l.left === 'string' && typeof l.right === 'string' && typeof l.op === 'string'
}

/**
 * Sends one image to `/api/transcribe`. The image is never kept or logged here, and the
 * returned lines are only shown back to the teacher for confirmation.
 */
export async function transcribe(image: Blob, { signal }: { signal?: AbortSignal } = {}): Promise<TranscribeResult> {
  const body = new FormData()
  const name = image.type === 'image/png' ? 'drawing.png' : 'photo.jpg'
  body.append('image', image, name)
  let res: Response
  try {
    res = await fetch('/api/transcribe', { method: 'POST', body, signal })
  } catch (e) {
    if ((e as Error).name === 'AbortError') throw e
    return { ok: false, error: 'unavailable' }
  }
  if (res.status === 413) return { ok: false, error: 'too_large' }
  if (res.status === 422) return { ok: false, error: 'bad_image' }
  if (res.status === 429) {
    const after = Number(res.headers.get('Retry-After'))
    return { ok: false, error: 'rate_limited', ...(after > 0 && { retryAfter: after }) }
  }
  if (!res.ok) return { ok: false, error: 'unavailable' }
  let data: unknown
  try {
    data = await res.json()
  } catch {
    return { ok: false, error: 'unavailable' }
  }
  const d = data as { status?: unknown; reason?: unknown; lines?: unknown }
  const reason = typeof d.reason === 'string' ? d.reason : null
  const raw = Array.isArray(d.lines) ? d.lines.filter(isApiLine) : []
  if (d.status !== 'ok' || raw.length === 0) return { ok: true, status: 'unclear', reason }
  return {
    ok: true,
    status: 'ok',
    lines: raw.map((l) => ({
      left: l.left,
      right: l.right,
      op: l.op,
      uncertain: l.uncertain === true || !(l.confidence >= UNCERTAIN_BELOW),
    })),
  }
}
