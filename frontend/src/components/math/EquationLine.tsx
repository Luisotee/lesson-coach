import { useContext, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { NotebookContext } from '@/components/math/notebook-context'
import { renderNode, renderOp } from '@/components/math/render'
import { cn } from '@/lib/utils'
import { parseMath, parseOp } from '@/math/parse'
import { speakLine } from '@/math/speech'

/** Seconds between lines when they are written on. */
export const WRITE_ON_STAGGER = 0.8

function draw(src: string): ReactNode {
  const parsed = parseMath(src)
  return parsed.ok ? renderNode(parsed.value) : src
}

function drawOp(src: string): ReactNode {
  const parsed = parseOp(src)
  return parsed.ok ? renderOp(parsed.value) : src
}

/**
 * One handwritten line in a Notebook: `left = right` aligned on `=`, with the operation for
 * this line in the green margin (`| −5`). With no `right`, the line is an expression; a
 * `continued` expression starts with `=`. Must be a child of Notebook.
 */
export function EquationLine({
  left,
  right = '',
  op = '',
  index = 0,
  continued = false,
  className,
}: {
  left: string
  right?: string
  op?: string
  /** Position in the notebook; sets the write-on delay. */
  index?: number
  continued?: boolean
  className?: string
}) {
  const { t } = useTranslation()
  const { writeOn } = useContext(NotebookContext)
  const isEquation = right !== ''
  const label = speakLine({ left, right, op, continued }, t)

  return (
    <li className={cn('col-span-full grid min-h-[2.2em] grid-cols-subgrid items-center', className)}>
      <span
        role="math"
        aria-label={label}
        data-math="line"
        className={cn(
          'col-span-full grid grid-cols-subgrid items-center whitespace-nowrap',
          writeOn && 'motion-safe:animate-write',
        )}
        style={writeOn ? { animationDelay: `${index * WRITE_ON_STAGGER}s` } : undefined}
      >
        <span aria-hidden="true" className="justify-self-end">
          {isEquation ? draw(left) : null}
        </span>
        <span aria-hidden="true" className="justify-self-center">
          {isEquation || continued ? '=' : null}
        </span>
        <span aria-hidden="true" className="justify-self-start">
          {isEquation ? draw(right) : draw(left)}
        </span>
        <span aria-hidden="true" className="ps-[0.6em] text-[0.75em] font-bold text-pen-green">
          {op ? drawOp(op) : null}
        </span>
      </span>
    </li>
  )
}
