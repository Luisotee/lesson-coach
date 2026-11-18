import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { cn } from '@/lib/utils'

export interface Section {
  id: string
  label: string
}

/** Which section is in view, for `aria-current`. The first one until the page scrolls. */
function useActiveSection(ids: string[]): string | undefined {
  const [active, setActive] = useState<string | undefined>(ids[0])
  const key = ids.join(' ')
  useEffect(() => {
    if (typeof IntersectionObserver === 'undefined') return
    const visible = new Map<string, boolean>()
    const observer = new IntersectionObserver(
      (entries) => {
        for (const e of entries) visible.set(e.target.id, e.isIntersecting)
        const first = key.split(' ').find((id) => visible.get(id))
        if (first) setActive(first)
      },
      { rootMargin: '-30% 0px -60% 0px' },
    )
    for (const id of key.split(' ')) {
      const el = document.getElementById(id)
      if (el) observer.observe(el)
    }
    return () => observer.disconnect()
  }, [key])
  return active
}

/**
 * "On this page": a side list on wide screens, a sticky scrolling strip on tablets and phones
 * (the tablet design's section tabs, kept as links so every section stays printable and
 * findable).
 */
export function SectionNav({ sections }: { sections: Section[] }) {
  const { t } = useTranslation()
  const active = useActiveSection(sections.map((s) => s.id))
  return (
    <nav
      aria-label={t('topic.onThisPage')}
      className="-mx-4 overflow-x-auto border-y border-line bg-white/70 px-4 py-2 print:hidden lg:sticky lg:top-[calc(var(--header-h,4.5rem)+0.75rem)] lg:mx-0 lg:w-56 lg:flex-none lg:self-start lg:overflow-visible lg:rounded-2xl lg:border lg:bg-white lg:p-2"
    >
      <span className="hidden px-3 py-2 text-xs font-semibold text-muted-foreground lowercase lg:block">
        {t('topic.onThisPage')}
      </span>
      <ul className="flex gap-1 lg:flex-col lg:gap-0.5">
        {sections.map((s) => (
          <li key={s.id}>
            <a
              href={`#${s.id}`}
              aria-current={active === s.id ? 'true' : undefined}
              className={cn(
                'flex min-h-11 items-center rounded-[10px] border border-transparent px-3 text-[15px] whitespace-nowrap text-[#3a4458] no-underline hover:border-line-strong hover:bg-[#eef1f4]',
                active === s.id && 'border-paleblue bg-paleblue/50 font-semibold text-navy',
              )}
            >
              {s.label}
            </a>
          </li>
        ))}
      </ul>
    </nav>
  )
}
