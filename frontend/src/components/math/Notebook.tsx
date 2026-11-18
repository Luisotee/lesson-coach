import type { ReactNode } from 'react'
import { EquationLine } from '@/components/math/EquationLine'
import { NotebookContext } from '@/components/math/notebook-context'
import { penClass, type PenVariant } from '@/components/math/pens'
import { cn } from '@/lib/utils'
import type { Step } from '@/math/types'

/**
 * Squared paper with handwritten lines. Lines are a list whose rows share one grid, so every
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
  return (
    <div
      dir="ltr"
      className={cn(
        'paper font-hand rounded-2xl border border-border px-4 py-5 text-2xl sm:px-6 sm:text-3xl',
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
          // An expression that follows another expression is written as "= …".
          continued={!step.right && i > 0 && !steps[i - 1].right}
        />
      ))}
    </Notebook>
  )
}
