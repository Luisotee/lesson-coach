import type { Ref } from 'react'

/** The API's MathIn: what one typed or confirmed expression is sent as. */
export type MathIn = { text: string } | { latex: string }

/** The API's LineIn: a confirmed transcribed line (plain-text step) or a typed line (LaTeX). */
export type LineIn = { left: string; right?: string; op?: string } | { latex: string }

export type InputMode = 'type' | 'write' | 'photo'

export interface ConfirmedExpression {
  mode: InputMode
  math: MathIn
}

/** 1 to 20 lines. */
export interface ConfirmedLines {
  mode: InputMode
  lines: LineIn[]
}

export interface MathInputHandle {
  /** Moves focus to the active mode's main control, for page validation. */
  focus(): void
}

interface MathInputBase {
  /** Visible label of the whole input group, e.g. "The problem". Also names the tabs and fields. */
  label: string
  /** Hint under the label, e.g. "Type fractions with a slash, like 2/5." */
  description?: string
  /**
   * The button that uses what was read from a drawing or photo, worded for the field, e.g.
   * "Use this problem". Default "Use this" (expression) or "Use these lines" (lines).
   */
  confirmLabel?: string
  /** A validation message from the page; shown and linked with aria-describedby. */
  error?: string
  /** Modes offered, in order. Default ['type', 'write', 'photo']. 'type' is always included. */
  modes?: InputMode[]
  /** Default 'type'. Practice uses 'write'. */
  defaultMode?: InputMode
  className?: string
  ref?: Ref<MathInputHandle>
}

export type MathInputProps =
  | (MathInputBase & {
      shape: 'expression'
      onChange: (value: ConfirmedExpression | null) => void
    })
  | (MathInputBase & { shape: 'lines'; onChange: (value: ConfirmedLines | null) => void })

/** One line as the confirm screen holds it: plain text, the Steps contract. */
export interface ReviewLine {
  left: string
  right: string
  op: string
  uncertain: boolean
}

/** API limits (backend/app/api/models.py). */
export const LIMITS = { text: 200, latex: 400, op: 30, lines: 20 } as const
