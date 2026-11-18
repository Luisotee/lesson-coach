import { render, screen } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import App from '@/App'

afterEach(() => vi.unstubAllGlobals())

test('renders the translated title and reports the API as connected', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn(() => Promise.resolve(new Response(JSON.stringify({ status: 'ok' }), { status: 200 }))),
  )
  render(<App />)
  expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('Lesson Coach')
  expect(await screen.findByText('connected')).toBeInTheDocument()
})
