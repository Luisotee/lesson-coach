import { ShieldCheck } from 'lucide-react'
import { MotionConfig } from 'motion/react'
import type { MouseEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, NavLink, Outlet, ScrollRestoration, useMatch } from 'react-router'
import { LanguagePicker } from '@/components/shell/LanguagePicker'
import { useRouteFocus } from '@/components/shell/hooks'
import { isTopicId, problemNumber } from '@/content/topics'
import { cn } from '@/lib/utils'

const navClass = ({ isActive }: { isActive: boolean }) =>
  cn(
    'inline-flex min-h-11 items-center rounded-lg border border-transparent px-3.5 text-[15px] font-medium text-[#3a4458] transition-colors hover:border-line-strong hover:bg-[#eef1f4]',
    isActive && 'bg-paleblue text-navy',
  )

function focusMain(e: MouseEvent<HTMLAnchorElement>) {
  e.preventDefault()
  document.getElementById('main')?.focus()
}

/** Our own mark (not the Akelius logo): plus, minus, times and divide on a navy tile. */
function Mark() {
  return (
    <svg width="32" height="32" viewBox="0 0 32 32" aria-hidden="true">
      <rect x="1" y="1" width="30" height="30" rx="9" className="fill-navy" />
      <path
        d="M10 12h5M12.5 9.5v5M18 12h5M10 21h5M18 19.5l4 4M22 19.5l-4 4"
        stroke="#fff"
        strokeWidth="2"
        strokeLinecap="round"
      />
    </svg>
  )
}

export function Shell() {
  const { t } = useTranslation()
  // Topics and Practice link to one place but stand for a section: they are current on every
  // real page of it (not on a "Page not found" under it). aria-current="true", not "page",
  // because the link's own target is a different page.
  const topicMatch = useMatch('/topics/:id')
  const practiceMatch = useMatch('/practice/:topic/:n')
  const inTopics = isTopicId(topicMatch?.params.id)
  const inPractice =
    isTopicId(practiceMatch?.params.topic) && problemNumber(practiceMatch?.params.n) !== null
  useRouteFocus()
  return (
    <MotionConfig reducedMotion="user">
      <a
        href="#main"
        onClick={focusMain}
        className="sr-only z-50 rounded-lg bg-navy px-4 py-3 font-semibold text-white focus:not-sr-only focus:fixed focus:start-3 focus:top-3"
      >
        {t('shell.skipToContent')}
      </a>
      <div className="flex min-h-svh flex-col">
        <header className="sticky top-0 z-10 border-b border-line bg-ground/85 backdrop-blur-md print:hidden">
          <div className="mx-auto flex max-w-[1200px] flex-wrap items-center justify-between gap-3 px-4 py-3 sm:px-6">
            <Link
              to="/"
              className="flex min-h-11 items-center gap-2.5 rounded-lg text-navy no-underline"
            >
              <Mark />
              <span className="font-heading text-lg font-bold tracking-tight">
                {t('app.title')}
              </span>
            </Link>
            <nav aria-label={t('shell.mainNav')} className="flex flex-wrap items-center gap-1">
              <Link
                to={{ pathname: '/', hash: '#topics' }}
                className={navClass({ isActive: inTopics })}
                aria-current={inTopics ? 'true' : undefined}
              >
                {t('nav.topics')}
              </Link>
              <NavLink to="/mistake" className={navClass}>
                {t('nav.mistake')}
              </NavLink>
              <Link
                to="/practice/negative-numbers/1"
                className={navClass({ isActive: inPractice })}
                aria-current={inPractice ? 'true' : undefined}
              >
                {t('nav.practice')}
              </Link>
            </nav>
            <div className="flex flex-wrap items-center gap-3">
              <span className="inline-flex items-center gap-2 rounded-full border border-line bg-white px-3 py-1.5 text-[13px] text-muted-foreground">
                <ShieldCheck aria-hidden="true" className="size-3.5 text-green" />
                {t('shell.nothingSaved')}
              </span>
              <LanguagePicker />
            </div>
          </div>
        </header>
        <main id="main" tabIndex={-1} className="flex-1 outline-none">
          <Outlet />
        </main>
        <footer className="border-t border-line bg-white print:hidden">
          <div className="mx-auto flex max-w-[1200px] flex-wrap justify-between gap-3 px-4 py-7 text-sm text-muted-foreground sm:px-6">
            <span>{t('shell.footerNoScores')}</span>
            <span>{t('shell.footerChecked')}</span>
          </div>
        </footer>
      </div>
      <ScrollRestoration />
    </MotionConfig>
  )
}
