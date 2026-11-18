import { useContext, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { useContentLang } from '@/components/content-lang'
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

/** A hand-drawn ring around a line, in the marking colour (5:1 on white). */
function Circle({ numbered }: { numbered: boolean }) {
  // Spans the math columns (left, =, right), not the step number or the margin.
  return (
    <span
      aria-hidden="true"
      className="pointer-events-none relative row-start-1 self-stretch"
      style={{ gridColumn: numbered ? '2 / 5' : '1 / 4' }}
    >
      <svg
        data-mark="circle"
        className="absolute -inset-x-3 -inset-y-1 h-[calc(100%+0.5rem)] w-[calc(100%+1.5rem)] text-mark"
        viewBox="0 0 100 40"
        preserveAspectRatio="none"
        fill="none"
      >
        <path
          d="M6 22 C 6 6, 94 2, 96 18 C 98 34, 10 40, 4 24 C 3 16, 20 8, 40 7"
          stroke="currentColor"
          strokeWidth="2.5"
          strokeLinecap="round"
          vectorEffect="non-scaling-stroke"
          pathLength={1}
          className="[stroke-dasharray:1] motion-safe:animate-[draw_0.6s_ease-out_both]"
        />
      </svg>
    </span>
  )
}

export interface LineAnnotation {
  /** Rings the whole line, e.g. the first line that doesn't follow. */
  circle?: boolean
  /** A short note in the margin, in the marking colour. Spoken after the line. */
  note?: string
}

/**
 * One handwritten line in a Notebook: `left = right` aligned on `=`, with the operation for
 * this line in the green margin (`| −5`). With no `right`, the line is an expression; a
 * `continued` expression starts with `=`. Must be a child of Notebook.
 *
 * With `onSelect` the line is a toggle button (`aria-pressed`), still on the shared grid.
 */
export function EquationLine({
  left,
  right = '',
  op = '',
  index = 0,
  continued = false,
  onSelect,
  selected = false,
  annotate,
  className,
}: {
  left: string
  right?: string
  op?: string
  /** Position in the notebook; sets the write-on delay and the step number. */
  index?: number
  continued?: boolean
  onSelect?: () => void
  selected?: boolean
  annotate?: LineAnnotation
  className?: string
}) {
  const { t } = useTranslation()
  const { writeOn, numbered } = useContext(NotebookContext)
  // The note is diagnosis text: it takes that text's language, not the UI's.
  const noteLang = useContentLang()
  const line = parseLine({ left, right, op })
  const spoken = speakParsedLine(line, continued, t)
  const label = annotate?.note
    ? t('math.speech.withNote', { line: spoken, note: annotate.note })
    : spoken

  const cells = (
    <>
      {numbered && (
        <span
          aria-hidden="true"
          className={cn(
            'flex size-6 items-center justify-center justify-self-center rounded-full border-[1.5px] font-sans text-[11px] font-bold',
            selected ? 'border-navy bg-navy text-white' : 'border-pencil bg-[#eef1f4] text-pencil',
          )}
        >
          {index + 1}
        </span>
      )}
      <span aria-hidden="true" className="relative justify-self-end">
        {line.right ? draw(line.left, left) : null}
      </span>
      <span aria-hidden="true" className="relative justify-self-center">
        {line.right || continued ? '=' : null}
      </span>
      <span aria-hidden="true" className="relative justify-self-start">
        {line.right ? draw(line.right, right) : draw(line.left, left)}
      </span>
      <span aria-hidden="true" className="relative ps-[0.6em] text-[0.75em] font-bold">
        {line.op ? <span className="text-pen-green">{drawOp(line.op, op)}</span> : null}
        {annotate?.note ? (
          <span
            className="ms-2 inline-block font-normal whitespace-normal text-mark"
            data-mark="note"
            {...noteLang}
          >
            ← {annotate.note}
          </span>
        ) : null}
      </span>
    </>
  )

  const rowClass = cn(
    'relative col-span-full row-start-1 grid grid-cols-subgrid items-center whitespace-nowrap',
    writeOn && 'motion-safe:animate-write',
  )
  const rowStyle = writeOn ? { animationDelay: `${index * WRITE_ON_STAGGER}s` } : undefined

  return (
    <li
      className={cn(
        'relative col-span-full grid min-h-[2.2em] grid-cols-subgrid items-center',
        className,
      )}
    >
      {selected && (
        <span
          aria-hidden="true"
          className="absolute inset-y-1 start-8 end-2 origin-left rounded-[6px_14px_8px_12px] bg-highlight/55 motion-safe:animate-[marker_0.45s_ease-out_both]"
        />
      )}
      {annotate?.circle && <Circle numbered={numbered} />}
      {onSelect ? (
        // Named by its spoken text (not aria-label), so the visible handwriting, which is
        // hidden from screen readers, doesn't have to match a label.
        <button
          type="button"
          aria-pressed={selected}
          data-math="line"
          onClick={onSelect}
          className={cn(
            rowClass,
            'min-h-11 cursor-pointer rounded-lg text-start transition-colors hover:bg-paleblue/40',
          )}
          style={rowStyle}
        >
          <span className="sr-only">{label}</span>
          {cells}
        </button>
      ) : (
        <span role="math" aria-label={label} data-math="line" className={rowClass} style={rowStyle}>
          {cells}
        </span>
      )}
    </li>
  )
}
