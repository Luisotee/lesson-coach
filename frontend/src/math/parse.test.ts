import { describe, expect, test } from 'vitest'
import { parseMath, parseOp, showsDot } from '@/math/parse'
import type { MathNode } from '@/math/types'

/** A compact, fully bracketed form of the tree, to compare structure in one line. */
function show(n: MathNode): string {
  switch (n.type) {
    case 'num':
      return n.value
    case 'var':
      return n.name
    case 'neg':
      return `neg(${show(n.arg)})`
    case 'add':
      return `(${show(n.left)} ${n.op} ${show(n.right)})`
    case 'mul':
      return `(${show(n.left)} * ${show(n.right)})`
    case 'frac':
      return `frac(${show(n.num)}, ${show(n.den)})`
    case 'pow':
      return `pow(${show(n.base)}, ${show(n.exp)})`
    case 'group':
      return `[${show(n.inner)}]`
    case 'rel':
      return n.sides.map(show).join(' = ')
  }
}

function parsed(src: string): string {
  const r = parseMath(src)
  if (!r.ok) throw new Error(r.error)
  return show(r.value)
}

describe('parseMath', () => {
  test.each([
    ['2*x + 6 = 10', '((2 * x) + 6) = 10'],
    ['1/2 + 1/3', '(frac(1, 2) + frac(1, 3))'],
    ['(1+1)/(2+3)', 'frac([(1 + 1)], [(2 + 3)])'],
    ['-5 - (-3)', '(neg(5) - [neg(3)])'],
    ['(-2)*(-3)', '([neg(2)] * [neg(3)])'],
    ['5 - 3 - 1', '((5 - 3) - 1)'],
    ['3*2/5', 'frac((3 * 2), 5)'],
    ['2/3*x', '(frac(2, 3) * x)'],
    ['1/2/3', 'frac(frac(1, 2), 3)'],
    ['x**2', 'pow(x, 2)'],
    ['x^2', 'pow(x, 2)'],
    ['2^3^2', 'pow(2, pow(3, 2))'],
    ['-x**2', 'neg(pow(x, 2))'],
    ['2^-1', 'pow(2, neg(1))'],
    ['2x + 1', '((2 * x) + 1)'],
    ['3x^2', '(3 * pow(x, 2))'],
    ['2(x + 3)', '(2 * [(x + 3)])'],
    ['(x + 1)(x - 1)', '([(x + 1)] * [(x - 1)])'],
    ['0.5 + .25', '(0.5 + .25)'],
    ['x', 'x'],
    ['+3', '3'],
    [
      '1/2 + 1/3 = (1+1)/(2+3) = 2/5',
      '(frac(1, 2) + frac(1, 3)) = frac([(1 + 1)], [(2 + 3)]) = frac(2, 5)',
    ],
  ])('%s', (src, expected) => {
    expect(parsed(src)).toBe(expected)
  })

  test.each(['', '2 +', '(1 + 2', '1 + 2)', 'sqrt(4)', 'xy', '2 $ 3', '2 3', '=3'])(
    'rejects %j',
    (src) => {
      expect(parseMath(src).ok).toBe(false)
    },
  )
})

describe('parseOp', () => {
  test.each([
    ['-5', 'sub', '5'],
    ['+ 5', 'add', '5'],
    ['*3', 'mul', '3'],
    ['/3', 'div', '3'],
    ['*(-1)', 'mul', '[neg(1)]'],
    ['/(2*x)', 'div', '[(2 * x)]'],
  ])('%s', (src, kind, arg) => {
    const r = parseOp(src)
    expect(r.ok && r.value.kind).toBe(kind)
    expect(r.ok && show(r.value.arg)).toBe(arg)
  })

  test.each(['', '5', 'x = 2', '-'])('rejects %j', (src) => {
    expect(parseOp(src).ok).toBe(false)
  })
})

describe('showsDot', () => {
  const mul = (src: string) => {
    const r = parseMath(src)
    if (!r.ok || r.value.type !== 'mul') throw new Error(src)
    return showsDot(r.value.left, r.value.right)
  }
  test.each([
    ['3*x', false],
    ['2*(x + 3)', false],
    ['(x+1)*(x-1)', false],
    ['3*5', true],
    ['x*2', true],
    ['(-2)*(-3)', true],
    ['3*(-2)', true],
    ['x*(1/2)', false],
  ])('%s → %s', (src, dot) => {
    expect(mul(src)).toBe(dot)
  })
})
