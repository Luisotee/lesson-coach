import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, test, vi } from 'vitest'
import type { CheckWorkingResult, MistakeResult as Result } from '@/api/types'
import { RichText } from '@/components/RichText'
import { MistakeResult } from '@/components/mistake/MistakeResult'
import { CheckResult } from '@/components/practice/CheckResult'
import { HintLadder } from '@/components/practice/HintLadder'
import { createMemoryRouter } from 'react-router'
import { RouterProvider } from 'react-router/dom'
import { PACKS } from '@/test/api'
import allFollow from '@/test/fixtures/check/all-follow.json'
import badLine from '@/test/fixtures/check/bad-line.json'
import correct from '@/test/fixtures/mistake/correct.json'
import diagnosed from '@/test/fixtures/mistake/diagnosed.json'
import notSimplified from '@/test/fixtures/mistake/not-simplified.json'
import outOfScope from '@/test/fixtures/mistake/out-of-scope.json'
import slip from '@/test/fixtures/mistake/slip.json'
import unclear from '@/test/fixtures/mistake/unclear.json'
import type { ReactNode } from 'react'

afterEach(() => vi.unstubAllGlobals())

/** Renders inside a router, for components with links. */
function inRouter(ui: ReactNode) {
  const router = createMemoryRouter([{ path: '*', element: ui }])
  return render(<RouterProvider router={router} />)
}

test('RichText draws backtick math by hand and keeps the prose', () => {
  render(<RichText text="Is it bigger than `1/2`? Ask." />)
  expect(screen.getByRole('math', { name: 'one half' })).toBeInTheDocument()
  expect(screen.getByText(/Is it bigger than/)).toBeInTheDocument()
})

test('RichText with a stray backtick shows the text as written', () => {
  render(<RichText text="a `b" />)
  expect(screen.getByText('a `b')).toBeInTheDocument()
  expect(screen.queryByRole('math')).toBeNull()
})

describe('HintLadder', () => {
  const item = PACKS['linear-equations'].practice[0]

  test('opens one rung at a time, then the answer, and starts over', async () => {
    inRouter(<HintLadder item={item} topic="linear-equations" />)
    const list = screen.getByRole('list')
    expect(within(list).getAllByText('(not opened)')).toHaveLength(4)
    for (let i = 0; i < 3; i++)
      await userEvent.click(screen.getByRole('button', { name: 'Show next hint' }))
    expect(within(list).getAllByText('(not opened)')).toHaveLength(1)
    await userEvent.click(screen.getByRole('button', { name: 'Show the answer' }))
    expect(within(list).queryAllByText('(not opened)')).toHaveLength(0)
    expect(screen.getByRole('link', { name: 'Open the worked example.' })).toHaveAttribute(
      'href',
      '/topics/linear-equations#example',
    )
    await userEvent.click(screen.getByRole('button', { name: 'Start over' }))
    expect(within(list).getAllByText('(not opened)')).toHaveLength(4)
    expect(screen.getByRole('button', { name: 'Show next hint' })).toHaveFocus()
  })
})

describe('CheckResult', () => {
  test('all lines follow, and the last line is the answer', () => {
    render(<CheckResult result={allFollow as CheckWorkingResult} />)
    expect(screen.getByText(/Every line follows/)).toBeInTheDocument()
    expect(screen.getByText('And the last line is the answer.')).toBeInTheDocument()
  })

  test('the first line that doesn’t follow is named and circled', () => {
    const { container } = render(<CheckResult result={badLine as CheckWorkingResult} />)
    expect(screen.getByText(/Line 2 doesn’t follow/)).toBeInTheDocument()
    const lines = screen.getAllByRole('listitem')
    expect(lines[1].querySelector('[data-mark="circle"]')).not.toBeNull()
    expect(container.querySelectorAll('[data-mark="circle"]')).toHaveLength(1)
  })
})

describe('MistakeResult', () => {
  const show = (r: unknown, topic?: string) =>
    inRouter(<MistakeResult result={r as Result} topic={topic} onTryAnother={() => {}} />)

  test('diagnosed: the reason, their working circled with a note, the answer, what to say, try next', () => {
    show(diagnosed, 'fractions')
    expect(screen.getByRole('heading', { level: 2 })).toHaveTextContent(
      'To add fractions, add the tops and add the bottoms.',
    )
    expect(screen.getByText('checked: this rule gives exactly their answer')).toBeInTheDocument()
    const wrote = screen.getByRole('list', { name: 'what they wrote' })
    const items = within(wrote).getAllByRole('listitem')
    expect(items[1].querySelector('[data-mark="circle"]')).not.toBeNull()
    expect(within(items[1]).getByRole('math')).toHaveAccessibleName(/marked: added the bottoms too/)
    expect(screen.getByRole('list', { name: 'the answer, worked out' })).toBeInTheDocument()
    expect(screen.getByText('nudge')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /try next with your student/ })).toHaveAttribute(
      'href',
      '/topics/fractions#mistakes',
    )
  })

  test('correct', () => {
    show(correct)
    expect(screen.getByRole('heading', { level: 2 })).toHaveTextContent('Your student is right.')
  })

  test('not simplified shows both answers as equal', () => {
    show(notSimplified)
    expect(screen.getByRole('heading', { level: 2 })).toHaveTextContent('Your student is right.')
    expect(screen.getByRole('math', { name: /10 over 12 equals 5 sixths/ })).toBeInTheDocument()
  })

  test('unclear asks how they got it, with no invented reason', () => {
    show(unclear)
    expect(screen.getByRole('heading', { level: 2 })).toHaveTextContent('Ask how they got it.')
    expect(screen.queryByText(/likely reason/)).toBeNull()
    expect(screen.getByText('Talk me through your first step.')).toBeInTheDocument()
  })

  test('slip circles the first line that doesn’t follow', () => {
    show(slip)
    expect(screen.getByText('looks like a slip')).toBeInTheDocument()
    const items = within(screen.getByRole('list', { name: 'what they wrote' })).getAllByRole(
      'listitem',
    )
    expect(items[1].querySelector('[data-mark="circle"]')).not.toBeNull()
  })

  test('out of scope says so and why', () => {
    show(outOfScope)
    expect(screen.getByRole('heading', { level: 2 })).toHaveTextContent(
      'outside what the coach covers',
    )
    expect(screen.getByText('This kind of math isn’t covered yet.')).toBeInTheDocument()
  })

  test('Try another answer calls back', async () => {
    const onTryAnother = vi.fn()
    inRouter(<MistakeResult result={correct as Result} onTryAnother={onTryAnother} />)
    await userEvent.click(screen.getByRole('button', { name: 'Try another answer' }))
    expect(onTryAnother).toHaveBeenCalled()
  })
})
