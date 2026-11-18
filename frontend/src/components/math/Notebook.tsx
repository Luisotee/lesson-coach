import { useEffect, useRef, useState, type ReactNode } from 'react'
import { EquationLine } from '@/components/math/EquationLine'
import { NotebookContext } from '@/components/math/notebook-context'
import { penClass, type PenVariant } from '@/components/math/pens'
import { cn } from '@/lib/utils'
import { isContinued } from '@/math/parse'
import type { Step } from '@/math/types'

/**
 * Whether the element's content is wider than the element. Updates when either is resized
 * (the language, font or viewport changes).
 */
function useOverflowsX(ref: React.RefObject<HTMLElement | null>): boolean {
  const [overflows, setOverflows] = useState(false)
  useEffect(() => {
    const el = ref.current
    if (!el || typeof ResizeObserver === 'undefined') return
    const check = () => setOverflows(el.scrollWidth > el.clientWidth + 1)
    const observer = new ResizeObserver(check)
    observer.observe(el)
    if (el.firstElementChild) observer.observe(el.firstElementChild)
    check()
    return () => observer.disconnect()
  }, [ref])
  return overflows
}

/**
 * Squared paper with handwritten lines. A line too long for the screen scrolls inside the
 * notebook, never the page (WCAG 1.4.10); the scroll area then takes keyboard focus. Lines are a list whose rows share one grid, so every
 * `=` sits in the same column. The page around it may be right to left; the math never is.
 */
export function Notebook({
  label,
  pen = 'ink',
  writeOn = false,
  className,
  children,
}: {
  /** Names the list for screen readers, e.g. "Worked example 1". */
  label: string
  pen?: PenVariant
  /** Writes the lines on one after another; off under prefers-reduced-motion. */
  writeOn?: boolean
  className?: string
  children: ReactNode
}) {
  const ref = useRef<HTMLDivElement>(null)
  const scrollable = useOverflowsX(ref)
  return (
    <div
      ref={ref}
      dir="ltr"
      {...(scrollable && { tabIndex: 0, role: 'region', 'aria-label': label })}
      data-scrollable={scrollable || undefined}
      className={cn(
        'paper font-hand overflow-x-auto rounded-2xl border border-border bg-local px-4 py-5 text-2xl sm:px-6 sm:text-3xl',
        penClass[pen],
        className,
      )}
      data-pen={pen}
    >
      <ol
        aria-label={label}
        className="grid grid-cols-[max-content_max-content_max-content_1fr] items-center gap-x-[0.35em] gap-y-1"
      >
        <NotebookContext value={{ writeOn }}>{children}</NotebookContext>
      </ol>
    </div>
  )
}

/** A notebook for a list of steps from a pack: `{left, right, op}` each. */
export function StepsNotebook({
  steps,
  ...props
}: { steps: readonly Step[] } & Omit<Parameters<typeof Notebook>[0], 'children'>) {
  return (
    <Notebook {...props}>
      {steps.map((step, i) => (
        <EquationLine
          key={i}
          index={i}
          left={step.left}
          right={step.right}
          op={step.op}
          continued={isContinued(steps, i)}
        />
      ))}
    </Notebook>
  )
}
