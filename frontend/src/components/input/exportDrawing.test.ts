import { expect, test } from 'vitest'
import { strokeBounds } from '@/components/input/exportDrawing'

test('strokeBounds covers every point plus the padding', () => {
  const strokes = [
    {
      points: [
        [10, 20, 0.5],
        [30, 5, 0.5],
      ] as [number, number, number][],
      pressure: false,
    },
    { points: [[50, 40, 0.5]] as [number, number, number][], pressure: true },
  ]
  expect(strokeBounds(strokes, 4)).toEqual({ x: 6, y: 1, w: 48, h: 43 })
  expect(strokeBounds([], 4)).toBeNull()
})
