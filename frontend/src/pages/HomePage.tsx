import { ArrowRight, BookOpen, CircleHelp, PenLine } from 'lucide-react'
import { motion, useReducedMotion } from 'motion/react'
import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router'
import { useApiLang, useTopics } from '@/api/queries'
import type { TopicSummary } from '@/api/types'
import { useGradeLabel } from '@/components/Grades'
import { LoadError, Loading } from '@/components/LoadState'
import { MathExpr } from '@/components/math'
import { usePageTitle } from '@/components/shell/hooks'
import { TOPIC_GLYPHS } from '@/content/topics'
import { findLanguage } from '@/i18n/languages'
import { cn } from '@/lib/utils'

const ease = [0.2, 0.8, 0.2, 1] as const

function FadeUp({
  delay = 0,
  className,
  children,
}: {
  delay?: number
  className?: string
  children: ReactNode
}) {
  // Under reduced motion everything is simply there: no fade, no slide.
  const reduce = useReducedMotion()
  return (
    <motion.div
      className={className}
      initial={reduce ? false : { opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.7, delay, ease }}
    >
      {children}
    </motion.div>
  )
}

/** The h1 with the translator's highlighted word marked in yellow. */
function HeroTitle() {
  const { t } = useTranslation()
  const title = t('home.title')
  const mark = t('home.titleHighlight')
  const at = mark ? title.indexOf(mark) : -1
  return (
    <h1 className="text-[clamp(40px,5.4vw,68px)] leading-[1.02] font-bold tracking-[-0.035em]">
      {at < 0 ? (
        title
      ) : (
        <>
          {title.slice(0, at)}
          <span className="bg-[linear-gradient(transparent_62%,var(--color-highlight)_62%,var(--color-highlight)_90%,transparent_90%)]">
            {mark}
          </span>
          {title.slice(at + mark.length)}
        </>
      )}
    </h1>
  )
}

/** The hero picture: a real worked example in miniature, linking to it. */
function HeroExample() {
  const { t } = useTranslation()
  return (
    <Link
      to="/topics/linear-equations#example"
      className="group relative block h-[380px] min-w-0 flex-[1_1_400px] text-navy no-underline"
    >
      <span className="sr-only">{t('home.heroExampleLink')}</span>
      <span aria-hidden="true" className="contents">
        <span className="absolute start-10 end-0 top-6 bottom-0 rounded-[28px] border border-line bg-[radial-gradient(120%_120%_at_0%_0%,var(--color-paleblue)_0%,#fff_60%)]" />
        <span className="absolute start-0 top-14 w-[min(360px,88%)] rounded-[20px] border border-line bg-white p-[22px] shadow-[0_30px_60px_-30px_rgba(23,43,83,.35)] motion-safe:animate-[floaty_7s_ease-in-out_infinite]">
          <span className="block text-xs font-semibold text-muted-foreground lowercase">
            {t('home.heroWorked')}
          </span>
          <span className="mt-3.5 flex flex-col gap-2.5 text-2xl" dir="ltr">
            <MathExpr expr="3*x + 5 = 20" className="text-pencil" />
            <span className="-mx-3 flex items-center justify-between gap-3 rounded-xl bg-paleblue/60 px-3 py-2.5">
              <MathExpr expr="3*x = 15" />
              <span className="rounded-full border border-paleblue bg-white px-2.5 py-1 font-sans text-[13px] font-semibold">
                {t('topic.modes.why')}
              </span>
            </span>
            <MathExpr expr="x = 5" className="text-pencil" />
          </span>
        </span>
        <span className="absolute end-0 bottom-[18px] w-[min(300px,80%)] rounded-[18px] bg-navy px-5 py-[18px] text-ground shadow-[0_24px_50px_-24px_rgba(23,43,83,.6)]">
          <span className="block text-[13px] font-semibold text-highlight">
            {t('home.heroWhyTitle')}
          </span>
          <span className="mt-2 block text-[15px] leading-normal">{t('home.heroWhyText')}</span>
        </span>
      </span>
    </Link>
  )
}

function TopicCard({ topic, index }: { topic: TopicSummary; index: number }) {
  const { t } = useTranslation()
  const grade = useGradeLabel(topic.grades)
  const glyph = TOPIC_GLYPHS[topic.id]
  const reduce = useReducedMotion()
  // Only the topic's own text is marked when it is in another language; "Open topic" is UI.
  const uiLang = useApiLang()
  const packLang =
    topic.lang === uiLang ? {} : { lang: topic.lang, dir: findLanguage(topic.lang).dir }
  return (
    <motion.li
      initial={reduce ? false : { opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.7, delay: 0.05 + index * 0.07, ease }}
    >
      <Link
        to={`/topics/${topic.id}`}
        className="flex h-full flex-col gap-[18px] rounded-[20px] border border-line bg-white p-6 text-navy no-underline transition-[transform,box-shadow] duration-300 hover:-translate-y-1 hover:shadow-[0_18px_40px_-18px_rgba(23,43,83,.28)] motion-reduce:hover:translate-y-0"
      >
        {glyph && (
          <span
            className={cn(
              'flex h-[120px] items-center justify-center rounded-[14px] text-[40px]',
              glyph.tone,
            )}
          >
            <MathExpr expr={glyph.expr} />
          </span>
        )}
        <span className="flex flex-col gap-1.5">
          {grade && (
            <span className="text-[13px] font-semibold text-muted-foreground">{grade}</span>
          )}
          <span className="font-heading text-[22px] font-semibold tracking-tight" {...packLang}>
            {topic.title}
          </span>
          {topic.summary && (
            <span className="text-[15px] leading-normal text-muted-foreground" {...packLang}>
              {topic.summary}
            </span>
          )}
        </span>
        <span className="mt-auto inline-flex items-center gap-2 text-[15px] font-semibold">
          {t('home.openTopic')}
          <ArrowRight aria-hidden="true" className="size-4 rtl:-scale-x-100" />
        </span>
      </Link>
    </motion.li>
  )
}

function TopicList() {
  const { t } = useTranslation()
  const topics = useTopics()
  if (topics.isPending) return <Loading />
  if (topics.isError)
    return <LoadError error={topics.error} onRetry={() => void topics.refetch()} />
  if (!topics.data.length) return <p>{t('home.noTopics')}</p>
  return (
    <ul className="grid grid-cols-[repeat(auto-fit,minmax(min(280px,100%),1fr))] gap-5">
      {topics.data.map((topic, i) => (
        <TopicCard key={topic.id} topic={topic} index={i} />
      ))}
    </ul>
  )
}

export function HomePage() {
  const { t } = useTranslation()
  usePageTitle()
  const ways = [
    {
      to: { hash: '#topics' },
      icon: BookOpen,
      tone: 'bg-paleblue',
      title: t('home.prepareTitle'),
      text: t('home.prepareText'),
    },
    {
      to: '/mistake',
      icon: PenLine,
      tone: 'bg-[#fffbeb] text-[#b45309]',
      title: t('home.mistakeTitle'),
      text: t('home.mistakeText'),
    },
    {
      to: '/practice',
      icon: CircleHelp,
      tone: 'bg-[#ecfdf5] text-green-text',
      title: t('home.practiceTitle'),
      text: t('home.practiceText'),
    },
  ]
  return (
    <div className="mx-auto flex max-w-[1200px] flex-col px-4 sm:px-6">
      <section className="flex flex-wrap items-center gap-14 pt-14 pb-14 sm:pt-[72px]">
        <div className="flex min-w-0 flex-[1_1_460px] flex-col gap-6">
          <FadeUp className="self-start">
            <span className="inline-flex items-center gap-2 rounded-full bg-paleblue/60 px-3 py-1.5 text-[13px] font-semibold">
              <span aria-hidden="true" className="size-1.5 rounded-full bg-navy" />
              {t('home.eyebrow')}
            </span>
          </FadeUp>
          <FadeUp delay={0.08}>
            <HeroTitle />
          </FadeUp>
          <FadeUp delay={0.16}>
            <p className="max-w-[34rem] text-[19px] leading-relaxed text-muted-foreground">
              {t('home.intro')}
            </p>
          </FadeUp>
          <FadeUp delay={0.24} className="flex flex-wrap gap-3">
            <Link
              to={{ hash: '#topics' }}
              className="inline-flex min-h-12 items-center gap-2.5 rounded-xl bg-navy px-[22px] font-semibold text-white no-underline transition-transform hover:-translate-y-px active:translate-y-px motion-reduce:transform-none"
            >
              {t('home.prepareTitle')}
              <ArrowRight aria-hidden="true" className="size-[18px] rtl:-scale-x-100" />
            </Link>
            <Link
              to="/mistake"
              className="inline-flex min-h-12 items-center rounded-xl border border-line bg-white px-5 font-semibold text-navy no-underline hover:border-line-strong hover:bg-[#eef1f4]"
            >
              {t('home.mistakeCta')}
            </Link>
          </FadeUp>
        </div>
        <HeroExample />
      </section>

      <section
        id="topics"
        aria-labelledby="topics-heading"
        className="flex flex-col gap-6 pt-6 pb-16"
      >
        <div className="flex flex-wrap items-end justify-between gap-3">
          <h2 id="topics-heading" className="text-[32px] font-semibold tracking-tight">
            {t('home.topicsHeading')}
          </h2>
          <p className="text-[15px] text-muted-foreground">{t('home.topicsIntro')}</p>
        </div>
        <TopicList />
      </section>

      <section aria-labelledby="ways-heading" className="pb-[72px]">
        <h2 id="ways-heading" className="sr-only">
          {t('home.waysHeading')}
        </h2>
        <ul className="grid grid-cols-[repeat(auto-fit,minmax(min(260px,100%),1fr))] gap-4">
          {ways.map(({ to, icon: Icon, tone, title, text }) => (
            <li key={title}>
              <Link
                to={to}
                className="flex h-full gap-4 rounded-[18px] border border-line bg-white p-[22px] text-navy no-underline transition-[transform,box-shadow] duration-300 hover:-translate-y-1 hover:shadow-[0_18px_40px_-18px_rgba(23,43,83,.28)] motion-reduce:hover:translate-y-0"
              >
                <span
                  className={cn(
                    'flex size-11 flex-none items-center justify-center rounded-xl',
                    tone,
                  )}
                >
                  <Icon aria-hidden="true" className="size-[22px]" />
                </span>
                <span className="flex flex-col gap-1">
                  <span className="font-semibold">{title}</span>
                  <span className="text-sm leading-normal text-muted-foreground">{text}</span>
                </span>
              </Link>
            </li>
          ))}
        </ul>
      </section>
    </div>
  )
}
