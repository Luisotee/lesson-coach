import { useContext, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { NotebookContext } from '@/components/math/notebook-context'
import { renderNode, renderOp } from '@/components/math/render'
import { cn } from '@/lib/utils'
import { parseLine } from '@/math/parse'
import { speakParsedLine } from '@/math/speech'
import type { MarginOp, MathNode, ParseResult } from '@/math/types'

/** Seconds between lines when they are written on. */
export const WRITE_ON_STAGGER = 0.8

function draw(parsed: ParseResult<MathNode>, src: string): ReactNode {
  return parsed.ok ? renderNode(parsed.value) : src
}

function drawOp(parsed: ParseResult<MarginOp>, src: string): ReactNode {
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
  const line = parseLine({ left, right, op })
  const label = speakParsedLine(line, continued, t)

  return (
    <li
      className={cn('col-span-full grid min-h-[2.2em] grid-cols-subgrid items-center', className)}
    >
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
          {line.right ? draw(line.left, left) : null}
        </span>
        <span aria-hidden="true" className="justify-self-center">
          {line.right || continued ? '=' : null}
        </span>
        <span aria-hidden="true" className="justify-self-start">
          {line.right ? draw(line.right, right) : draw(line.left, left)}
        </span>
        <span aria-hidden="true" className="ps-[0.6em] text-[0.75em] font-bold text-pen-green">
          {line.op ? drawOp(line.op, op) : null}
        </span>
      </span>
    </li>
  )
}
