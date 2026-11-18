import type { ReactNode } from 'react'
import { Fraction } from '@/components/math/Fraction'
import { showsDot } from '@/math/parse'
import type { MarginOp, MathNode } from '@/math/types'

const MINUS = '−'

/** An operator with the small gaps handwriting leaves around it. */
const Sym = ({ children }: { children: ReactNode }) => <span className="mx-[0.22em]">{children}</span>

/** Drops parentheses that a stacked fraction makes unnecessary: (1 + 1)/(2 + 3). */
const unwrap = (n: MathNode): MathNode => (n.type === 'group' ? n.inner : n)

/** Draws the tree exactly as written: no evaluation, no reordering. */
export function renderNode(node: MathNode): ReactNode {
  switch (node.type) {
    case 'num':
      return node.value
    case 'var':
      return <i>{node.name}</i>
    case 'neg':
      return (
        <>
          {MINUS}
          {renderNode(node.arg)}
        </>
      )
    case 'add':
      return (
        <>
          {renderNode(node.left)}
          <Sym>{node.op === '+' ? '+' : MINUS}</Sym>
          {renderNode(node.right)}
        </>
      )
    case 'mul':
      return (
        <>
          {renderNode(node.left)}
          {showsDot(node.left, node.right) && <Sym>·</Sym>}
          {renderNode(node.right)}
        </>
      )
    case 'frac':
      return <Fraction num={renderNode(unwrap(node.num))} den={renderNode(unwrap(node.den))} />
    case 'pow':
      return (
        <>
          {renderNode(node.base)}
          <sup className="text-[0.6em]">{renderNode(unwrap(node.exp))}</sup>
        </>
      )
    case 'group':
      return (
        <>
          ({renderNode(node.inner)})
        </>
      )
    case 'rel':
      return node.sides.map((side, i) => (
        <span key={i}>
          {i > 0 && <Sym>=</Sym>}
          {renderNode(side)}
        </span>
      ))
  }
}

const OP_SYMBOLS: Record<MarginOp['kind'], string> = { add: '+', sub: MINUS, mul: '·', div: '÷' }

/** A margin note such as `| −5` or `| ÷ 3`. */
export function renderOp(op: MarginOp): ReactNode {
  return (
    <>
      <span className="me-[0.3em]">|</span>
      {OP_SYMBOLS[op.kind]}
      <span className="ms-[0.15em]">{renderNode(op.arg)}</span>
    </>
  )
}
