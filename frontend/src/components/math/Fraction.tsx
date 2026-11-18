import type { ReactNode } from 'react'
import { cn } from '@/lib/utils'

/** A stacked fraction drawn by hand: numerator, a bar in the pen's colour, denominator. */
export function Fraction({
  num,
  den,
  className,
}: {
  num: ReactNode
  den: ReactNode
  className?: string
}) {
  return (
    <span
      className={cn(
        'mx-[0.12em] inline-flex flex-col items-center align-middle leading-[1.05]',
        className,
      )}
      data-math="fraction"
    >
      <span className="px-[0.22em] pb-[0.08em]">{num}</span>
      <span className="border-t-2 border-current px-[0.22em] pt-[0.08em]">{den}</span>
    </span>
  )
}
