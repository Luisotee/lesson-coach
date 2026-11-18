import type { MarginOp, MathNode, OpKind, ParseResult } from '@/math/types'

/**
 * A small parser for the sympy plain-text strings of the Steps contract: numbers, single-letter
 * variables, + - * / and ** (or ^), parentheses, unary minus, implicit products (`2x`, `2(x + 1)`)
 * and `=`. It only builds a tree to draw; it never evaluates or simplifies. Anything else
 * (functions, multi-letter names) is an error, and the caller shows the text as written.
 *
 * One deviation from sympy's grammar, for drawing only: an integer over an integer (`2/3`) binds
 * tighter than `*`, so `2/3*4/5` is drawn as a product of two fractions and `3*2/5` as 3 · ⅖,
 * as a fractions lesson means them. The value is the same either way.
 */

type Token =
  | { kind: 'num'; value: string }
  | { kind: 'ident'; value: string }
  | { kind: 'op'; value: '+' | '-' | '*' | '/' | '^' | '(' | ')' | '=' }

export function tokenize(src: string): Token[] {
  const tokens: Token[] = []
  let i = 0
  while (i < src.length) {
    const c = src[i]
    if (/\s/.test(c)) {
      i++
    } else if (/[0-9.]/.test(c)) {
      const m = /^(\d+(\.\d+)?|\.\d+)/.exec(src.slice(i))
      if (!m) throw new Error(`Bad number at ${i}`)
      tokens.push({ kind: 'num', value: m[0] })
      i += m[0].length
    } else if (/[A-Za-z]/.test(c)) {
      const m = /^[A-Za-z_][A-Za-z0-9_]*/.exec(src.slice(i))!
      tokens.push({ kind: 'ident', value: m[0] })
      i += m[0].length
    } else if (c === '*' && src[i + 1] === '*') {
      tokens.push({ kind: 'op', value: '^' })
      i += 2
    } else if ('+-*/^()='.includes(c)) {
      tokens.push({ kind: 'op', value: c as '+' })
      i++
    } else {
      throw new Error(`Unexpected '${c}' at ${i}`)
    }
  }
  return tokens
}

// Binding powers. Unary minus binds looser than a power, so -x**2 is -(x**2) as in sympy.
const ADD = 10
const MUL = 20
const NEG = 30
const POW = 40

class Parser {
  private pos = 0
  private readonly tokens: Token[]
  constructor(tokens: Token[]) {
    this.tokens = tokens
  }

  private peek(): Token | undefined {
    return this.tokens[this.pos]
  }

  private isOp(value: string): boolean {
    const t = this.peek()
    return t?.kind === 'op' && t.value === value
  }

  private next(): Token {
    const t = this.tokens[this.pos++]
    if (!t) throw new Error('Unexpected end of input')
    return t
  }

  done(): boolean {
    return this.pos >= this.tokens.length
  }

  relation(): MathNode {
    const sides = [this.expr(0)]
    while (this.isOp('=')) {
      this.next()
      sides.push(this.expr(0))
    }
    return sides.length === 1 ? sides[0] : { type: 'rel', sides }
  }

  expr(minBp: number): MathNode {
    let left = this.prefix(minBp)
    for (;;) {
      const t = this.peek()
      if (!t) break
      if (t.kind === 'op' && (t.value === '+' || t.value === '-')) {
        if (ADD <= minBp) break
        this.next()
        left = { type: 'add', op: t.value, left, right: this.expr(ADD + 1) }
      } else if (t.kind === 'op' && (t.value === '*' || t.value === '/')) {
        if (MUL <= minBp) break
        this.next()
        const right = this.expr(MUL + 1)
        left =
          t.value === '*' ? { type: 'mul', left, right } : { type: 'frac', num: left, den: right }
      } else if (t.kind === 'op' && t.value === '^') {
        if (POW < minBp) break
        this.next()
        // Right-associative: 2^3^2 is 2^(3^2).
        left = { type: 'pow', base: left, exp: this.expr(POW) }
      } else if (t.kind === 'ident' || (t.kind === 'op' && t.value === '(')) {
        // Implicit product: 2x, 3(x + 1), (x + 1)(x - 1).
        if (MUL <= minBp) break
        left = { type: 'mul', left, right: this.expr(MUL + 1) }
      } else {
        break
      }
    }
    return left
  }

  /** True when the next tokens are `/ <integer>` not followed by `^` (2/3^2 is 2/(3^2)). */
  private integerDenominatorFollows(): boolean {
    const [slash, den, after] = this.tokens.slice(this.pos, this.pos + 3)
    return (
      slash?.kind === 'op' &&
      slash.value === '/' &&
      den?.kind === 'num' &&
      /^\d+$/.test(den.value) &&
      !(after?.kind === 'op' && after.value === '^')
    )
  }

  private prefix(minBp: number): MathNode {
    const t = this.next()
    if (t.kind === 'num') {
      const num: MathNode = { type: 'num', value: t.value }
      // int/int is one fraction, except inside an exponent (2^3/4 is (2^3)/4).
      if (minBp < POW && /^\d+$/.test(t.value) && this.integerDenominatorFollows()) {
        this.next()
        return { type: 'frac', num, den: { type: 'num', value: this.next().value } }
      }
      return num
    }
    if (t.kind === 'ident') {
      if (t.value.length !== 1) throw new Error(`Unsupported name '${t.value}'`)
      return { type: 'var', name: t.value }
    }
    if (t.value === '-') return { type: 'neg', arg: this.expr(NEG) }
    if (t.value === '+') return { type: 'pos', arg: this.expr(NEG) }
    if (t.value === '(') {
      const inner = this.expr(0)
      if (!this.isOp(')')) throw new Error('Missing )')
      this.next()
      return { type: 'group', inner }
    }
    throw new Error(`Unexpected '${t.value}'`)
  }
}

export function parseMath(src: string): ParseResult<MathNode> {
  try {
    const parser = new Parser(tokenize(src))
    const value = parser.relation()
    if (!parser.done()) throw new Error('Unexpected input after the expression')
    return { ok: true, value }
  } catch (e) {
    return { ok: false, error: (e as Error).message }
  }
}

const OP_KINDS: Record<string, OpKind> = { '+': 'add', '-': 'sub', '*': 'mul', '/': 'div' }

/** Parses a margin operation such as `-5`, `+5`, `*3`, `/3` or `*(-1)`. */
export function parseOp(src: string): ParseResult<MarginOp> {
  const m = /^\s*([-+*/])\s*(.+)$/.exec(src)
  if (!m) return { ok: false, error: 'An operation starts with + - * or /' }
  const arg = parseMath(m[2])
  if (!arg.ok) return arg
  if (arg.value.type === 'rel') return { ok: false, error: 'An operation has no =' }
  return { ok: true, value: { kind: OP_KINDS[m[1]], arg: arg.value } }
}

/** True when the node, as drawn, starts with a digit or a minus sign. */
export function startsWithNumber(node: MathNode): boolean {
  switch (node.type) {
    case 'num':
    case 'neg':
    case 'pos':
      return true
    case 'var':
    case 'group':
      return false
    case 'add':
    case 'mul':
      return startsWithNumber(node.left)
    case 'frac':
      return true // a stacked fraction is read as a number
    case 'pow':
      return startsWithNumber(node.base)
    case 'rel':
      return startsWithNumber(node.sides[0])
  }
}

export function hasVariable(node: MathNode): boolean {
  switch (node.type) {
    case 'num':
      return false
    case 'var':
      return true
    case 'neg':
    case 'pos':
      return hasVariable(node.arg)
    case 'group':
      return hasVariable(node.inner)
    case 'add':
    case 'mul':
      return hasVariable(node.left) || hasVariable(node.right)
    case 'frac':
      return hasVariable(node.num) || hasVariable(node.den)
    case 'pow':
      return hasVariable(node.base) || hasVariable(node.exp)
    case 'rel':
      return node.sides.some(hasVariable)
  }
}

/**
 * Whether a product is drawn with a dot. `3x` and `2(x + 3)` are written side by side;
 * `3 · 5`, `x · 2` and `(−2) · (−3)` need the dot to be read correctly.
 */
export function showsDot(left: MathNode, right: MathNode): boolean {
  return startsWithNumber(right) || (!hasVariable(left) && !hasVariable(right))
}

/** Drops brackets a layout already shows: a whole numerator, denominator or exponent. */
export function unwrapGroup(node: MathNode): MathNode {
  return node.type === 'group' ? node.inner : node
}

/** One notebook line, parsed once for both the drawing and the spoken text. */
export interface ParsedLine {
  left: ParseResult<MathNode>
  /** Absent for an expression step. */
  right?: ParseResult<MathNode>
  /** Absent when the line has no margin operation. */
  op?: ParseResult<MarginOp>
  /** The original text, shown and spoken as written when it doesn't parse. */
  source: { left: string; right: string; op: string }
}

export function parseLine({
  left,
  right = '',
  op = '',
}: {
  left: string
  right?: string
  op?: string
}): ParsedLine {
  return {
    left: parseMath(left),
    right: right ? parseMath(right) : undefined,
    op: op ? parseOp(op) : undefined,
    source: { left, right, op },
  }
}

/** An expression step that follows another expression step is written as "= …". */
export function isContinued(steps: readonly { right: string }[], i: number): boolean {
  return !steps[i].right && i > 0 && !steps[i - 1].right
}
