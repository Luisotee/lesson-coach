/** One worked step, as stored in the packs: sympy-parsable plain text, never LaTeX. */
export interface Step {
  left: string
  /** Empty for an expression step (no `=`). */
  right: string
  /** The margin operation applied to this line, such as `-5`, `/3`, `*2`; empty for none. */
  op: string
}

/** The render tree for one expression. Parentheses the author wrote are kept as `group`. */
export type MathNode =
  | { type: 'num'; value: string }
  | { type: 'var'; name: string }
  | { type: 'neg'; arg: MathNode }
  /** An explicit plus sign, as in 5 − (+3). */
  | { type: 'pos'; arg: MathNode }
  | { type: 'add'; op: '+' | '-'; left: MathNode; right: MathNode }
  | { type: 'mul'; left: MathNode; right: MathNode }
  | { type: 'frac'; num: MathNode; den: MathNode }
  | { type: 'pow'; base: MathNode; exp: MathNode }
  | { type: 'group'; inner: MathNode }
  | { type: 'rel'; sides: MathNode[] }

export type OpKind = 'add' | 'sub' | 'mul' | 'div'

export interface MarginOp {
  kind: OpKind
  arg: MathNode
}

export type ParseResult<T> = { ok: true; value: T } | { ok: false; error: string }
