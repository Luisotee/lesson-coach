import { act, render, screen, within } from '@testing-library/react'
import { StrictMode } from 'react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import { createMemoryRouter } from 'react-router'
import { RouterProvider } from 'react-router/dom'
import i18n from '@/i18n'
import { routes } from '@/router'
import { mockApi } from '@/test/api'

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
])('%s shows "%s"', (path, heading) => {
  renderAt(path)
  expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent(heading)
})

test('practice has previous and next only where a problem exists', () => {
  renderAt('/practice/fractions/1')
  expect(screen.queryByRole('link', { name: /Previous problem/ })).toBeNull()
  expect(screen.getByRole('link', { name: /Next problem/ })).toHaveAttribute(
    'href',
    '/practice/fractions/2',
  )
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
  expect(await screen.findByRole('link', { name: 'المواضيع' })).toBeInTheDocument()
  expect(document.documentElement).toHaveAttribute('dir', 'rtl')
  expect(screen.getByLabelText('اللغة')).toHaveValue('ar')
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

test('the practice page title is one translated message', () => {
  renderAt('/practice/fractions/2')
  expect(document.title).toBe('Practice: Fractions, Problem 2 of 8 · Lesson Coach')
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
