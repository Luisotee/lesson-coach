import type { ReactNode } from 'react'
import { cn } from '@/lib/utils'

export type PenVariant = 'pencil' | 'ink' | 'green'

/** Pencil grey for student work, navy ink for worked examples, green pen for corrections. */
export const penClass: Record<PenVariant, string> = {
  pencil: 'text-pencil',
  ink: 'text-ink',
  green: 'text-pen-green',
}

export function Pen({
  variant = 'ink',
  as: Tag = 'span',
  className,
  children,
}: {
  variant?: PenVariant
  as?: 'span' | 'div'
  className?: string
  children: ReactNode
}) {
  return (
    <Tag className={cn('font-hand', penClass[variant], className)} data-pen={variant}>
      {children}
    </Tag>
  )
}
