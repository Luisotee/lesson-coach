import { expect, test } from 'vitest'
import {
  canRedo,
  canUndo,
  emptyHistory,
  historyReducer as r,
  visibleStrokes,
  type Stroke,
} from '@/components/input/strokes'

const s = (x: number): Stroke => ({ points: [[x, x, 0.5]], pressure: false })

test('undo and redo walk the history; a new stroke drops the redo stack', () => {
  let h = r(r(emptyHistory, { type: 'add', stroke: s(1) }), { type: 'add', stroke: s(2) })
  expect(visibleStrokes(h)).toEqual([s(1), s(2)])
  h = r(h, { type: 'undo' })
  expect(visibleStrokes(h)).toEqual([s(1)])
  expect(canRedo(h)).toBe(true)
  h = r(h, { type: 'redo' })
  expect(visibleStrokes(h)).toEqual([s(1), s(2)])
  h = r(r(h, { type: 'undo' }), { type: 'add', stroke: s(3) })
  expect(visibleStrokes(h)).toEqual([s(1), s(3)])
  expect(canRedo(h)).toBe(false)
})

test('clear is undoable, and clearing an empty board does nothing', () => {
  expect(r(emptyHistory, { type: 'clear' })).toBe(emptyHistory)
  let h = r(emptyHistory, { type: 'add', stroke: s(1) })
  h = r(h, { type: 'clear' })
  expect(visibleStrokes(h)).toEqual([])
  expect(canUndo(h)).toBe(true)
  h = r(h, { type: 'undo' })
  expect(visibleStrokes(h)).toEqual([s(1)])
})

test('undo and redo at the ends change nothing', () => {
  expect(r(emptyHistory, { type: 'undo' })).toBe(emptyHistory)
  expect(r(emptyHistory, { type: 'redo' })).toBe(emptyHistory)
  expect(r(r(emptyHistory, { type: 'add', stroke: s(1) }), { type: 'reset' })).toEqual(emptyHistory)
})
