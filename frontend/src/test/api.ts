import { vi } from 'vitest'
import type { Pack, TopicSummary } from '@/api/types'
import fractions from '@/test/fixtures/packs/fractions.json'
import linear from '@/test/fixtures/packs/linear-equations.json'
import negative from '@/test/fixtures/packs/negative-numbers.json'
import topicsFixture from '@/test/fixtures/topics.json'

// Typed against the API shapes, so a fixture that drifts from them fails `tsc`.
export const PACKS: Record<string, Pack> = {
  'negative-numbers': negative as Pack,
  fractions: fractions as Pack,
  'linear-equations': linear as Pack,
}
export const TOPICS: TopicSummary[] = topicsFixture as TopicSummary[]

type Handler = (url: URL, init?: RequestInit) => Response | Promise<Response>

export const json = (body: unknown, status = 200, headers: Record<string, string> = {}) =>
  new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json', ...headers } })

/**
 * Stubs `fetch` with the fixture API. `routes` override or add handlers by "METHOD /path".
 * Returns the mock, to inspect requests.
 */
export function mockApi(routes: Record<string, Handler> = {}) {
  const fn = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = new URL(String(input), 'http://localhost')
    const key = `${init?.method ?? 'GET'} ${url.pathname}`
    if (routes[key]) return routes[key](url, init)
    if (key === 'GET /api/topics') return json(TOPICS)
    const m = /^GET \/api\/topics\/([^/]+)$/.exec(key)
    if (m) return PACKS[m[1]] ? json(PACKS[m[1]]) : json({ detail: 'not found' }, 404)
    return json({ detail: 'not mocked' }, 404)
  })
  vi.stubGlobal('fetch', fn)
  return fn
}
