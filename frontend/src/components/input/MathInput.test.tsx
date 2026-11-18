import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, test, vi } from 'vitest'
import { MathInput } from '@/components/input/MathInput'
import { TranscriptionReview } from '@/components/input/TranscriptionReview'

// MathLive needs a real browser (e2e covers it); here it "fails to load", which exercises the
// plain-text fallback the component promises.
vi.mock('@/components/input/mathlive', () => ({
  loadMathLive: () => Promise.reject(new Error('no MathLive in jsdom')),
}))

test('three tabs in the WAI-ARIA pattern; arrow keys switch modes', async () => {
  const user = userEvent.setup()
  render(<MathInput shape="expression" label="The problem" onChange={() => {}} />)
  const tabs = screen.getAllByRole('tab')
  expect(tabs.map((t) => t.textContent)).toEqual(['Type', 'Write', 'Photo'])
  expect(tabs[0]).toHaveAttribute('aria-selected', 'true')
  await user.click(tabs[0])
  await user.keyboard('{ArrowRight}')
  expect(screen.getByRole('tab', { name: 'Write' })).toHaveAttribute('aria-selected', 'true')
  expect(
    screen.getByRole('img', { name: /Drawing board for The problem: empty/ }),
  ).toBeInTheDocument()
})

test('typed math is reported as it changes; the value follows the active tab', async () => {
  const user = userEvent.setup()
  const onChange = vi.fn()
  render(<MathInput shape="expression" label="The answer" onChange={onChange} />)
  const field = await screen.findByRole('textbox', { name: 'The answer' })
  expect(field).toHaveAttribute('dir', 'ltr')
  await user.type(field, '2/5')
  expect(onChange).toHaveBeenLastCalledWith({ mode: 'type', math: { text: '2/5' } })
  await user.click(screen.getByRole('tab', { name: 'Photo' }))
  expect(onChange).toHaveBeenLastCalledWith(null)
  await user.click(screen.getByRole('tab', { name: 'Type' }))
  expect(onChange).toHaveBeenLastCalledWith({ mode: 'type', math: { text: '2/5' } })
  await user.clear(field)
  expect(onChange).toHaveBeenLastCalledWith(null)
})

test('"Type it instead" switches to typing and focuses the field', async () => {
  const user = userEvent.setup()
  render(
    <MathInput shape="expression" label="The problem" defaultMode="photo" onChange={() => {}} />,
  )
  await user.click(screen.getByRole('button', { name: 'Type it instead' }))
  expect(screen.getByRole('tab', { name: 'Type' })).toHaveAttribute('aria-selected', 'true')
  expect(await screen.findByRole('textbox', { name: 'The problem' })).toHaveFocus()
})

test('typed lines are reported per line; an empty line is skipped', async () => {
  const user = userEvent.setup()
  const onChange = vi.fn()
  render(<MathInput shape="lines" label="Working" onChange={onChange} />)
  await user.type(await screen.findByRole('textbox', { name: 'Working, line 1' }), '2x+6=10')
  await user.click(screen.getByRole('button', { name: 'Add a line' }))
  await user.click(screen.getByRole('button', { name: 'Add a line' }))
  await user.type(await screen.findByRole('textbox', { name: 'Working, line 3' }), 'x=2')
  expect(onChange).toHaveBeenLastCalledWith({
    mode: 'type',
    lines: [
      { left: '2x+6', right: '10' },
      { left: 'x', right: '2' },
    ],
  })
  await user.click(screen.getByRole('button', { name: 'Remove line 1' }))
  expect(onChange).toHaveBeenLastCalledWith({ mode: 'type', lines: [{ left: 'x', right: '2' }] })
})

const read = [
  { left: '1/2 + 1/3', right: '', op: '', uncertain: false },
  { left: '2/5', right: '', op: '', uncertain: true },
]

test('the confirm screen marks uncertain lines in text and needs one line for an expression', async () => {
  const user = userEvent.setup()
  const onConfirm = vi.fn()
  render(
    <TranscriptionReview
      initial={read}
      single
      retakeLabel="Draw again"
      onConfirm={onConfirm}
      onUnconfirm={() => {}}
      onRetake={() => {}}
    />,
  )
  expect(screen.getByText('1 line needs a check.')).toBeInTheDocument()
  const list = screen.getByRole('list', { name: 'Lines that were read' })
  const lines = [...list.children]
  expect(lines.map((li) => li.hasAttribute('data-uncertain'))).toEqual([false, true])
  expect(within(lines[1] as HTMLElement).getByText('check this line')).toBeInTheDocument()

  const confirm = screen.getByRole('button', { name: 'Yes, use these lines' })
  expect(confirm).toHaveAttribute('aria-disabled', 'true')
  expect(screen.getByText(/Keep only one line here/)).toBeInTheDocument()
  await user.click(confirm)
  expect(onConfirm).not.toHaveBeenCalled()

  await user.click(screen.getByRole('button', { name: 'Remove line 1' }))
  await user.click(confirm)
  expect(onConfirm).toHaveBeenCalledWith([
    expect.objectContaining({ left: '2/5', right: '', op: '' }),
  ])
  expect(screen.getByText('Confirmed.')).toBeInTheDocument()
})

test('editing a line after confirming takes the confirmation back', async () => {
  const user = userEvent.setup()
  const onConfirm = vi.fn()
  const onUnconfirm = vi.fn()
  render(
    <TranscriptionReview
      initial={[{ left: '2*x + 6', right: '10', op: '-6', uncertain: true }]}
      single={false}
      retakeLabel="Draw again"
      onConfirm={onConfirm}
      onUnconfirm={onUnconfirm}
      onRetake={() => {}}
    />,
  )
  await user.click(screen.getByRole('button', { name: 'Yes, use these lines' }))
  expect(onConfirm).toHaveBeenCalledTimes(1)
  await user.click(screen.getByRole('button', { name: 'Edit line 1' }))
  const left = screen.getByRole('textbox', { name: 'Left side' })
  expect(left).toHaveFocus()
  await user.clear(left)
  await user.type(left, '2*x + 4')
  expect(onUnconfirm).toHaveBeenCalledTimes(1)
  await user.click(screen.getByRole('button', { name: 'Done editing line 1' }))
  expect(screen.queryByText('check this line')).not.toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: 'Yes, use these lines' }))
  expect(onConfirm).toHaveBeenLastCalledWith([
    expect.objectContaining({ left: '2*x + 4', right: '10', op: '-6' }),
  ])
})

test('a confirmed transcription reaches the page as the API shape', async () => {
  const user = userEvent.setup()
  const onChange = vi.fn()
  vi.stubGlobal(
    'fetch',
    vi.fn(
      async () =>
        new Response(
          JSON.stringify({
            status: 'ok',
            reason: null,
            lines: [{ left: '2*x + 6', right: '10', op: '-6', confidence: 0.9, uncertain: false }],
          }),
        ),
    ),
  )
  // jsdom has no canvas: give the export a 2D context that does nothing, and toBlob a blob.
  vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue({
    fillRect: () => {},
    fill: () => {},
    setTransform: () => {},
    clearRect: () => {},
  } as never)
  vi.spyOn(HTMLCanvasElement.prototype, 'toBlob').mockImplementation((cb) =>
    cb(new Blob(['png'], { type: 'image/png' })),
  )
  vi.stubGlobal(
    'Path2D',
    class {
      moveTo() {}
      lineTo() {}
      closePath() {}
    },
  )
  render(<MathInput shape="lines" label="Working" defaultMode="write" onChange={onChange} />)
  const canvas = screen.getByRole('img', { name: /empty/ })
  canvas.setPointerCapture = () => {}
  canvas.getBoundingClientRect = () => ({ left: 0, top: 0 }) as DOMRect
  const pointer = { pointerId: 1, pointerType: 'touch', clientX: 10, clientY: 10, button: 0 }
  const { fireEvent } = await import('@testing-library/react')
  fireEvent.pointerDown(canvas, pointer)
  fireEvent.pointerMove(canvas, { ...pointer, clientX: 40 })
  fireEvent.pointerUp(canvas, pointer)
  expect(screen.getByRole('img', { name: /1 stroke/ })).toBeInTheDocument()

  await user.click(screen.getByRole('button', { name: 'Read my writing' }))
  await user.click(await screen.findByRole('button', { name: 'Yes, use these lines' }))
  expect(onChange).toHaveBeenLastCalledWith({
    mode: 'write',
    lines: [{ left: '2*x + 6', right: '10', op: '-6' }],
  })
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})
