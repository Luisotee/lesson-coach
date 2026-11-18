import { expect, test } from 'vitest'
import { clampRect, displayToImage, growRect, initialCrop, moveRect, resizeRect } from '@/components/input/crop'

const bounds = { w: 100, h: 50 }

test('a move stops at the edges', () => {
  expect(moveRect({ x: 10, y: 10, w: 20, h: 20 }, 200, -50, bounds)).toEqual({ x: 80, y: 0, w: 20, h: 20 })
})

test('dragging a corner keeps the opposite corner and the minimum size', () => {
  const r = { x: 10, y: 10, w: 40, h: 30 }
  expect(resizeRect(r, 'nw', 5, 5, bounds, 8)).toEqual({ x: 15, y: 15, w: 35, h: 25 })
  expect(resizeRect(r, 'se', 100, 100, bounds, 8)).toEqual({ x: 10, y: 10, w: 90, h: 40 })
  expect(resizeRect(r, 'ne', -100, 0, bounds, 8)).toEqual({ x: 10, y: 10, w: 8, h: 30 })
  expect(resizeRect(r, 'sw', -50, -100, bounds, 8)).toEqual({ x: 0, y: 10, w: 50, h: 8 })
})

test('growing from the keyboard resizes from the bottom-right corner', () => {
  expect(growRect({ x: 0, y: 0, w: 10, h: 10 }, -20, 5, bounds, 4)).toEqual({ x: 0, y: 0, w: 4, h: 15 })
})

test('clamp keeps a rectangle inside and at least the minimum', () => {
  expect(clampRect({ x: -5, y: 40, w: 200, h: 0 }, bounds, 2)).toEqual({ x: 0, y: 40, w: 100, h: 2 })
})

test('display coordinates map back to whole image pixels inside the image', () => {
  expect(displayToImage({ x: 10, y: 5, w: 50, h: 20 }, 0.5, { w: 120, h: 60 })).toEqual({ x: 20, y: 10, w: 100, h: 40 })
  expect(displayToImage({ x: 0, y: 0, w: 100, h: 50 }, 0.5, { w: 199, h: 99 })).toEqual({ x: 0, y: 0, w: 199, h: 99 })
})

test('the first crop is the image less a margin', () => {
  expect(initialCrop({ w: 200, h: 100 }, 0.1)).toEqual({ x: 20, y: 10, w: 160, h: 80 })
})
