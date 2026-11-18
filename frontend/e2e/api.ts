import { readFileSync } from 'node:fs'
import type { Page, Route } from '@playwright/test'

/** The fixture API (`src/test/fixtures`), served at the network layer. Live LLM calls can't be in e2e. */
const fixtures = new URL('../src/test/fixtures/', import.meta.url)
const read = (path: string): unknown => JSON.parse(readFileSync(new URL(path, fixtures), 'utf8'))

export const PACKS: Record<string, unknown> = Object.fromEntries(
  ['negative-numbers', 'fractions', 'linear-equations'].map((id) => [id, read(`packs/${id}.json`)]),
)

const fulfil = (route: Route, body: unknown, status = 200, headers: Record<string, string> = {}) =>
  route.fulfill({ status, contentType: 'application/json', headers, body: JSON.stringify(body) })

export interface ApiOverrides {
  mistake?: (body: unknown) => { status?: number; body: unknown; headers?: Record<string, string> }
  checkWorking?: (body: unknown) => { status?: number; body: unknown }
}

/** Mocks the API for one page. Returns the request bodies posted, for assertions. */
export async function mockApi(page: Page, overrides: ApiOverrides = {}) {
  const posted: { url: string; body: unknown }[] = []
  await page.route('**/api/topics**', (route) => {
    const url = new URL(route.request().url())
    if (url.pathname === '/api/topics') return fulfil(route, read('topics.json'))
    const id = decodeURIComponent(url.pathname.split('/').pop() ?? '')
    return PACKS[id] ? fulfil(route, PACKS[id]) : fulfil(route, { detail: 'Not Found' }, 404)
  })
  await page.route('**/api/mistake', (route) => {
    const body = route.request().postDataJSON()
    posted.push({ url: '/api/mistake', body })
    const r = overrides.mistake?.(body) ?? { body: read('mistake/diagnosed.json') }
    return fulfil(route, r.body, r.status, r.headers)
  })
  await page.route('**/api/check-working', (route) => {
    const body = route.request().postDataJSON()
    posted.push({ url: '/api/check-working', body })
    const r = overrides.checkWorking?.(body) ?? { body: read('check/all-follow.json') }
    return fulfil(route, r.body, r.status)
  })
  return posted
}

export const fixture = read
