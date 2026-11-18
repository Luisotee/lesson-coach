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

test.each(['x/2 + 1', '120/252', '15 + (-32)', '2*(x + 3)'])('no picture for %s', (left) => {
  expect(pictureFor({ left, right: '' })).toBeNull()
})
