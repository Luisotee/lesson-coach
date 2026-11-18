import { expect, test } from 'vitest'
import { latexValue, textValue, toExpression, toLineIns } from '@/components/input/lines'

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
})

test('typed values pass through as LaTeX or text, null when empty or too long', () => {
  expect(latexValue('\\frac{1}{2}')).toEqual({ latex: '\\frac{1}{2}' })
  expect(latexValue('  ')).toBeNull()
  expect(latexValue('\\frac{1}{\\placeholder{}}')).toBeNull()
  expect(latexValue('x'.repeat(401))).toBeNull()
  expect(textValue('1/2')).toEqual({ text: '1/2' })
  expect(textValue('x'.repeat(201))).toBeNull()
})
