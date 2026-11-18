import { afterEach, expect, test, vi } from 'vitest'
import { transcribe } from '@/components/input/transcribe'

const png = new Blob(['x'], { type: 'image/png' })

function respond(status: number, body?: unknown, headers: Record<string, string> = {}) {
  const fetchMock = vi.fn(
    async () => new Response(body === undefined ? null : JSON.stringify(body), { status, headers }),
  )
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

afterEach(() => vi.unstubAllGlobals())

test('posts the image as multipart and marks low-confidence lines uncertain', async () => {
  const fetchMock = respond(200, {
    status: 'ok',
    reason: null,
    lines: [
      { left: '2*x + 6', right: '10', op: '-6', confidence: 0.95, uncertain: false },
      { left: '2*x', right: '4', op: '', confidence: 0.5, uncertain: false },
      { left: 'x', right: '2', op: '', confidence: 0.9, uncertain: true },
    ],
  })
  const result = await transcribe(png)
  const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit]
  expect(url).toBe('/api/transcribe')
  expect(init.method).toBe('POST')
  expect((init.body as FormData).get('image')).toBeInstanceOf(Blob)
  expect(result).toEqual({
    ok: true,
    status: 'ok',
    lines: [
      { left: '2*x + 6', right: '10', op: '-6', uncertain: false },
      { left: '2*x', right: '4', op: '', uncertain: true },
      { left: 'x', right: '2', op: '', uncertain: true },
    ],
  })
})

test('unclear, or ok with no lines, is unclear', async () => {
  respond(200, { status: 'unclear', reason: 'ai_unavailable', lines: [] })
  expect(await transcribe(png)).toEqual({ ok: true, status: 'unclear', reason: 'ai_unavailable' })
  respond(200, { status: 'ok', reason: null, lines: [] })
  expect(await transcribe(png)).toEqual({ ok: true, status: 'unclear', reason: null })
})

test('HTTP errors map to honest errors', async () => {
  respond(413)
  expect(await transcribe(png)).toEqual({ ok: false, error: 'too_large' })
  respond(415)
  expect(await transcribe(png)).toEqual({ ok: false, error: 'bad_image' })
  respond(422, { detail: [] })
  expect(await transcribe(png)).toEqual({ ok: false, error: 'bad_image' })
  respond(429, { detail: 'slow down' }, { 'Retry-After': '30' })
  expect(await transcribe(png)).toEqual({ ok: false, error: 'rate_limited', retryAfter: 30 })
  respond(404)
  expect(await transcribe(png)).toEqual({ ok: false, error: 'unavailable' })
})

test('a network failure is unavailable; an abort is rethrown', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn(async () => Promise.reject(new TypeError('Failed to fetch'))),
  )
  expect(await transcribe(png)).toEqual({ ok: false, error: 'unavailable' })
  vi.stubGlobal(
    'fetch',
    vi.fn(async () => Promise.reject(new DOMException('aborted', 'AbortError'))),
  )
  await expect(transcribe(png)).rejects.toThrow('aborted')
})
