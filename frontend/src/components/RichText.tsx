import { Fragment } from 'react'
import { useContentLang } from '@/components/content-lang'
import { MathExpr } from '@/components/math/MathExpr'
import { cn } from '@/lib/utils'

/**
 * Prose from a pack or the API, with inline math in backticks drawn by hand:
 * "Is it bigger than `1/2`?". Math that doesn't parse is shown as written.
 */
export function RichText({
  text,
  as: Tag = 'span',
  className,
}: {
  text: string
  as?: 'span' | 'p' | 'div'
  className?: string
}) {
  const lang = useContentLang()
  const parts = text.split('`')
  // An odd number of backticks leaves a stray one: show the text as written.
  if (parts.length % 2 === 0)
    return (
      <Tag className={className} {...lang}>
        {text}
      </Tag>
    )
  return (
    <Tag className={className} {...lang}>
      {parts.map((part, i) =>
        i % 2 === 1 ? (
          <MathExpr key={i} expr={part} className={cn('mx-0.5 text-[1.15em] leading-none')} />
        ) : (
          <Fragment key={i}>{part}</Fragment>
        ),
      )}
    </Tag>
  )
}
