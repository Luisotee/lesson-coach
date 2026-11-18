import { expect, test } from 'vitest'
import { lineIssue, mathIssue, toExpression, toLineIns, toMath } from '@/components/input/lines'

const line = (left: string, right = '', op = '') => ({ left, right, op, uncertain: false })

test('reviewed lines become steps; blanks are dropped and fields trimmed', () => {
  expect(toLineIns([line(' 2*x + 6 ', '10', '-6'), line('  ', ' '), line('2*x', '4')])).toEqual([
    { left: '2*x + 6', right: '10', op: '-6' },
    { left: '2*x', right: '4' },
  ])
})

test('one line becomes one expression without its margin operation', () => {
  expect(toExpression(line('2*x + 6', '10', '-6'))).toEqual({ text: '2*x + 6 = 10' })
  expect(toExpression(line('2/5'))).toEqual({ text: '2/5' })
  expect(toExpression(line(' ', '5'))).toEqual({ text: '5' })
})

test('typed values pass through as LaTeX or text, null when empty, unfinished or too long', () => {
  expect(toMath({ latex: '\\frac{1}{2}' })).toEqual({ latex: '\\frac{1}{2}' })
  expect(toMath({ latex: '  ' })).toBeNull()
  expect(mathIssue({ latex: '\\frac{1}{\\placeholder{}}' })).toBe('emptyBox')
  expect(toMath({ latex: '\\frac{1}{\\placeholder{}}' })).toBeNull()
  expect(mathIssue({ latex: 'x'.repeat(401) })).toBe('tooLong')
  expect(toMath({ text: '1/2' })).toEqual({ text: '1/2' })
  expect(mathIssue({ text: 'x'.repeat(201) })).toBe('tooLong')
})

test('a reviewed line is too long when a side or its operation is over the limit', () => {
  expect(lineIssue(line('x'.repeat(200), '1', '-1'))).toBeNull()
  expect(lineIssue(line('x', 'y'.repeat(201)))).toBe('tooLong')
  expect(lineIssue(line('x', '1', '-' + '1'.repeat(30)))).toBe('tooLong')
})
