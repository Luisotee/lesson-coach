import { expect, test } from 'vitest'
import { pictureFor } from '@/components/visual/picture'

test('an equation is a balance with its written terms', () => {
  const p = pictureFor({ left: '3*x + 5', right: '20' })
  expect(p?.kind).toBe('balance')
  if (p?.kind !== 'balance') return
  expect(p.left).toHaveLength(2)
  expect(p.right).toHaveLength(1)
})

test('integer fractions are bars', () => {
  expect(pictureFor({ left: '3/6 + 2/6', right: '' })).toEqual({
    kind: 'bars',
    terms: [
      { sign: 1, num: 3, den: 6 },
      { sign: 1, num: 2, den: 6 },
    ],
  })
})

test('small whole numbers are counters, with the written operator', () => {
  expect(pictureFor({ left: '5 - (-3)', right: '' })).toEqual({
    kind: 'counters',
    terms: [
      { sign: 1, n: 5 },
      { sign: -1, n: -3 },
    ],
  })
})

test.each([
  ['-5 + 3', [-5, 3], [1, 1]],
  ['-2', [-2], [1]],
  ['-3 - 2', [-3, 2], [1, -1]],
])('a leading minus is drawn: %s', (left, ns, signs) => {
  const p = pictureFor({ left, right: '' })
  expect(p?.kind).toBe('counters')
  if (p?.kind !== 'counters') return
  expect(p.terms.map((t) => t.n)).toEqual(ns)
  expect(p.terms.map((t) => t.sign)).toEqual(signs)
})

test('fractions with a leading minus have no bar picture', () => {
  expect(pictureFor({ left: '-1/2 + 3/4', right: '' })).toBeNull()
  expect(pictureFor({ left: '3/4 - 1/2', right: '' })?.kind).toBe('bars')
})

test.each(['x/2 + 1', '120/252', '15 + (-32)', '2*(x + 3)'])('no picture for %s', (left) => {
  expect(pictureFor({ left, right: '' })).toBeNull()
})
