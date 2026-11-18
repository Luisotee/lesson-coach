/** A point in CSS pixels of the board, with pen pressure from 0 to 1. */
export type Point = [x: number, y: number, pressure: number]

export interface Stroke {
  points: Point[]
  /** Real pressure from a pen; simulated from speed for mouse and touch. */
  pressure: boolean
}

/**
 * The drawing's history. `done` is every action so far, `undone` the ones undone (for redo).
 * Clearing is an action too, so it can be undone.
 */
export interface History {
  done: Action[]
  undone: Action[]
}

export type Action = { kind: 'stroke'; stroke: Stroke } | { kind: 'clear' }

export type HistoryEvent =
  | { type: 'add'; stroke: Stroke }
  | { type: 'undo' }
  | { type: 'redo' }
  | { type: 'clear' }
  | { type: 'reset' }

export const emptyHistory: History = { done: [], undone: [] }

export function historyReducer(state: History, event: HistoryEvent): History {
  switch (event.type) {
    case 'add':
      return { done: [...state.done, { kind: 'stroke', stroke: event.stroke }], undone: [] }
    case 'undo': {
      const last = state.done.at(-1)
      if (!last) return state
      return { done: state.done.slice(0, -1), undone: [...state.undone, last] }
    }
    case 'redo': {
      const next = state.undone.at(-1)
      if (!next) return state
      return { done: [...state.done, next], undone: state.undone.slice(0, -1) }
    }
    case 'clear':
      if (visibleStrokes(state).length === 0) return state
      return { done: [...state.done, { kind: 'clear' }], undone: [] }
    case 'reset':
      return emptyHistory
  }
}

/** The strokes on the board now: those after the last clear. */
export function visibleStrokes(state: History): Stroke[] {
  const strokes: Stroke[] = []
  for (const action of state.done) {
    if (action.kind === 'clear') strokes.length = 0
    else strokes.push(action.stroke)
  }
  return strokes
}

export const canUndo = (state: History) => state.done.length > 0
export const canRedo = (state: History) => state.undone.length > 0
