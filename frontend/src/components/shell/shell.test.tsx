import { act, render, screen, within } from '@testing-library/react'
import { StrictMode } from 'react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, test } from 'vitest'
import { createMemoryRouter } from 'react-router'
import { RouterProvider } from 'react-router/dom'
import i18n from '@/i18n'
import { routes } from '@/router'

afterEach(() => act(() => i18n.changeLanguage('en')))

function renderAt(path: string) {
  const router = createMemoryRouter(routes, { initialEntries: [path] })
  render(<RouterProvider router={router} />)
  return router
}

test('home links to every topic, the mistake explainer and practice', () => {
  renderAt('/')
  expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent(
    'Feel sure of the math before you teach it.',
  )
  expect(screen.getByRole('link', { name: /Negative numbers/ })).toHaveAttribute(
    'href',
    '/topics/negative-numbers',
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

test('the Practice link is current on every practice page', () => {
  renderAt('/practice/fractions/2')
  const nav = screen.getByRole('navigation', { name: 'Main' })
  expect(within(nav).getByRole('link', { name: 'Practice' })).toHaveAttribute(
    'aria-current',
    'page',
  )
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

test('following a link to the page you are on moves focus again', async () => {
  renderAt('/')
  const topics = screen.getByRole('link', { name: 'Topics' })
  await userEvent.click(topics)
  expect(document.getElementById('topics')).toHaveFocus()
  topics.focus()
  await userEvent.click(topics)
  expect(document.getElementById('topics')).toHaveFocus()
})
