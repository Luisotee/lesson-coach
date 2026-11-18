import { act, render, screen, waitFor, within } from '@testing-library/react'
import { StrictMode } from 'react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import { createMemoryRouter } from 'react-router'
import { RouterProvider } from 'react-router/dom'
import i18n from '@/i18n'
import { routes } from '@/router'
import { PACKS, json, mockApi } from '@/test/api'
import ar from '@/locales/ar.json'

beforeEach(() => {
  mockApi()
})

afterEach(async () => {
  vi.unstubAllGlobals()
  await act(() => i18n.changeLanguage('en'))
})

function renderAt(path: string) {
  const router = createMemoryRouter(routes, { initialEntries: [path] })
  render(<RouterProvider router={router} />)
  return router
}

test('home links to every topic from the API, the mistake explainer and practice', async () => {
  renderAt('/')
  expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent(
    'Feel sure of the math before you teach it.',
  )
  for (const [name, id] of [
    [/Negative numbers/, 'negative-numbers'],
    [/Fractions/, 'fractions'],
    [/Solving linear equations/, 'linear-equations'],
  ] as const) {
    expect(await screen.findByRole('link', { name })).toHaveAttribute('href', `/topics/${id}`)
  }
  expect(screen.getByText('Grade 7–8')).toBeInTheDocument()
  expect(screen.getByRole('link', { name: 'A student wrote this…' })).toHaveAttribute(
    'href',
    '/mistake',
  )
  expect(screen.getByRole('link', { name: 'Skip to main content' })).toBeInTheDocument()
  expect(document.title).toBe('Lesson Coach')
})

test.each([
  ['/topics/fractions', 'Fractions'],
  ['/mistake', 'A student wrote this'],
  ['/practice/linear-equations/3', 'Practice: Solving linear equations'],
  ['/demo/math', 'Math handwriting components'],
  ['/topics/algebra', 'Page not found'],
  ['/practice/fractions/9', 'Page not found'],
  ['/practice/fractions/0', 'Page not found'],
  ['/nowhere', 'Page not found'],
])('%s shows "%s"', async (path, heading) => {
  renderAt(path)
  await waitFor(() => expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent(heading))
})

test('practice has previous and next only where a problem exists', async () => {
  renderAt('/practice/fractions/1')
  expect(await screen.findByRole('link', { name: /Next problem/ })).toHaveAttribute(
    'href',
    '/practice/fractions/2',
  )
  expect(screen.queryByRole('link', { name: /Previous problem/ })).toBeNull()
})

test('navigating moves focus to the new page heading', async () => {
  renderAt('/')
  await userEvent.click(screen.getByRole('link', { name: 'A student wrote this' }))
  expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('A student wrote this')
  expect(screen.getByRole('heading', { level: 1 })).toHaveFocus()
})

test('the language picker switches the UI to Arabic, right to left', async () => {
  renderAt('/')
  await userEvent.selectOptions(screen.getByLabelText('Language'), 'ar')
  expect(await screen.findByRole('link', { name: ar.nav.topics })).toBeInTheDocument()
  expect(document.documentElement).toHaveAttribute('dir', 'rtl')
  expect(screen.getByLabelText(ar.language.label)).toHaveValue('ar')
})

test.each([
  ['/practice/fractions/2', 'Practice', 'true'],
  ['/practice/fractions/9', 'Practice', null],
  ['/topics/fractions', 'Topics', 'true'],
  ['/topics/algebra', 'Topics', null],
  ['/', 'Topics', null],
])('on %s the %s link has aria-current=%s', (path, name, current) => {
  renderAt(path)
  const nav = screen.getByRole('navigation', { name: 'Main' })
  const link = within(nav).getByRole('link', { name })
  if (current) expect(link).toHaveAttribute('aria-current', current)
  else expect(link).not.toHaveAttribute('aria-current')
})

test('the practice page title is one translated message', async () => {
  renderAt('/practice/fractions/2')
  await waitFor(() =>
    expect(document.title).toBe('Practice: Fractions, Problem 2 of 8 · Lesson Coach'),
  )
})

test('the first load leaves focus alone, even under StrictMode', () => {
  const router = createMemoryRouter(routes, { initialEntries: ['/mistake'] })
  render(
    <StrictMode>
      <RouterProvider router={router} />
    </StrictMode>,
  )
  expect(screen.getByRole('heading', { level: 1 })).not.toHaveFocus()
})

test('a malformed #hash does not break the page', async () => {
  const router = renderAt('/')
  await act(() => router.navigate('/mistake#%E0%A4%A'))
  expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('A student wrote this')
})

test('an unknown #target falls back to the page heading', async () => {
  const router = renderAt('/')
  await act(() => router.navigate('/mistake#nowhere'))
  expect(screen.getByRole('heading', { level: 1 })).toHaveFocus()
})

test('following a link to the page you are on moves focus again', async () => {
  renderAt('/')
  const topics = screen.getByRole('link', { name: 'Topics' })
  await userEvent.click(topics)
  expect(document.getElementById('topics')).toHaveFocus()
  topics.focus()
  await userEvent.click(topics)
  expect(document.getElementById('topics')).toHaveFocus()
})

test('a #section link into a topic that is still loading reaches the section once it loads', async () => {
  const router = renderAt('/')
  await act(() => router.navigate('/topics/linear-equations#example'))
  await waitFor(() => expect(document.getElementById('example')).toHaveFocus())
})

test('switching topics keeps working when the next pack is cached and had a later step chosen', async () => {
  const router = renderAt('/topics/fractions')
  await screen.findByRole('heading', { level: 1, name: 'Fractions' })
  await act(() => router.navigate('/topics/linear-equations'))
  await screen.findByRole('heading', { level: 1, name: 'Solving linear equations' })
  await userEvent.click(screen.getByRole('button', { name: 'Next worked example' }))
  const lines = within(document.getElementById('example')!).getAllByRole('button', {
    pressed: false,
  })
  await userEvent.click(lines[lines.length - 1])
  await act(() => router.navigate('/topics/fractions'))
  expect(await screen.findByRole('heading', { level: 1, name: 'Fractions' })).toBeInTheDocument()
  expect(screen.getByText('Worked example 1 of 3')).toBeInTheDocument()
})

test('Practice opens the first topic, in API order, that has practice problems', async () => {
  // The first topic ships without practice; its pack answers last.
  mockApi({
    'GET /api/topics/negative-numbers': async () => {
      await new Promise((r) => setTimeout(r, 50))
      return json({ ...PACKS['negative-numbers'], practice: [] })
    },
  })
  const router = renderAt('/practice')
  await waitFor(() => expect(router.state.location.pathname).toBe('/practice/fractions/1'))
})

test('Practice says so when no topic has practice problems', async () => {
  const empty = (id: string) => () => json({ ...PACKS[id], practice: [] })
  mockApi({
    'GET /api/topics/negative-numbers': empty('negative-numbers'),
    'GET /api/topics/fractions': empty('fractions'),
    'GET /api/topics/linear-equations': empty('linear-equations'),
  })
  renderAt('/practice')
  expect(await screen.findByText('There are no practice problems yet.')).toBeInTheDocument()
  expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('Practice')
})

test.each([
  ['/topics/fractions', 'Fractions · Lesson Coach'],
  ['/practice/fractions/2', 'Practice: Fractions · Lesson Coach'],
])('%s has its own title while loading and when loading fails', async (path, title) => {
  mockApi({ 'GET /api/topics/fractions': () => json({ detail: 'boom' }, 500) })
  renderAt(path)
  expect(document.title).toBe(title)
  await screen.findByRole('alert', {}, { timeout: 5000 })
  expect(document.title).toBe(title)
})
