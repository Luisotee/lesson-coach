import { parseMath } from '@/math/parse'
import type { MathNode } from '@/math/types'

/** The value in an answer such as `5`, `x = 5` or `-1/2`, for the variable it names. */
function answerValue(answer: string): { name?: string; value: MathNode } | null {
  const parsed = parseMath(answer)
  if (!parsed.ok) return null
  const node = parsed.value
  if (node.type !== 'rel') return { value: node }
  if (node.sides.length !== 2) return null
  const [a, b] = node.sides
  if (a.type === 'var') return { name: a.name, value: b }
  if (b.type === 'var') return { name: b.name, value: a }
  return null
}

function variables(node: MathNode, out = new Set<string>()): Set<string> {
  switch (node.type) {
    case 'var':
      out.add(node.name)
      break
    case 'num':
      break
    case 'neg':
    case 'pos':
      variables(node.arg, out)
      break
    case 'group':
      variables(node.inner, out)
      break
    case 'add':
    case 'mul':
      variables(node.left, out)
      variables(node.right, out)
      break
    case 'frac':
      variables(node.num, out)
      variables(node.den, out)
      break
    case 'pow':
      variables(node.base, out)
      variables(node.exp, out)
      break
    case 'rel':
      node.sides.forEach((s) => variables(s, out))
  }
  return out
}

function replace(node: MathNode, name: string, value: MathNode): MathNode {
  const r = (n: MathNode) => replace(n, name, value)
  switch (node.type) {
    case 'var':
      return node.name === name ? value : node
    case 'num':
      return node
    case 'neg':
    case 'pos':
      return { ...node, arg: r(node.arg) }
    case 'group':
      return { ...node, inner: r(node.inner) }
    case 'add':
    case 'mul':
      return { ...node, left: r(node.left), right: r(node.right) }
    case 'frac':
      return { ...node, num: r(node.num), den: r(node.den) }
    case 'pow':
      return { ...node, base: r(node.base), exp: r(node.exp) }
    case 'rel':
      return { ...node, sides: node.sides.map(r) }
  }
}

/**
 * The equation with the verified answer written in for its variable: `3*x + 5 = 20` with
 * `5` becomes `3 · 5 + 5 = 20`. This only redraws the given math; nothing is evaluated.
 * Returns null when the problem isn't one equation in one variable.
 */
export function substituteAnswer(equation: string, answer: string): MathNode | null {
  const eq = parseMath(equation)
  const ans = answerValue(answer)
  if (!eq.ok || !ans || eq.value.type !== 'rel') return null
  const names = variables(eq.value)
  if (names.size !== 1) return null
  const [name] = names
  if (ans.name && ans.name !== name) return null
  // A plain number or a fraction reads fine in place; anything signed or compound gets brackets.
  const simple = ans.value.type === 'num' || ans.value.type === 'frac'
  const value: MathNode = simple ? ans.value : { type: 'group', inner: ans.value }
  return replace(eq.value, name, value)
}
