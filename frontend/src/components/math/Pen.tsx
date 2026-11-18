import type { ReactNode } from 'react'
import { penClass, type PenVariant } from '@/components/math/pens'
import { cn } from '@/lib/utils'

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
