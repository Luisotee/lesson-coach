import { ArrowRight, BookOpen, CircleHelp, PenLine } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router'
import { usePageTitle } from '@/components/shell/hooks'
import { TOPIC_IDS } from '@/content/topics'

/** Foundation version of Home; T8 builds the full design on it. Every link works. */
export function HomePage() {
  const { t } = useTranslation()
  usePageTitle()
  const ways = [
    {
      to: `/topics/${TOPIC_IDS[0]}`,
      icon: BookOpen,
      title: t('home.prepareTitle'),
      text: t('home.prepareText'),
    },
    { to: '/mistake', icon: PenLine, title: t('home.mistakeTitle'), text: t('home.mistakeText') },
    {
      to: `/practice/${TOPIC_IDS[0]}/1`,
      icon: CircleHelp,
      title: t('home.practiceTitle'),
      text: t('home.practiceText'),
    },
  ]
  return (
    <div className="mx-auto flex max-w-[1200px] flex-col gap-14 px-4 py-14 sm:px-6">
      <section className="flex max-w-2xl flex-col gap-5">
        <span className="self-start rounded-full bg-paleblue px-3 py-1.5 text-[13px] font-semibold text-navy">
          {t('home.eyebrow')}
        </span>
        <h1 className="text-4xl font-bold tracking-tight sm:text-6xl">{t('home.title')}</h1>
        <p className="text-lg leading-relaxed text-muted-foreground">{t('home.intro')}</p>
      </section>

      <section
        id="topics"
        aria-labelledby="topics-heading"
        className="flex scroll-mt-24 flex-col gap-6"
      >
        <div className="flex flex-wrap items-end justify-between gap-3">
          <h2 id="topics-heading" className="text-3xl font-semibold tracking-tight">
            {t('home.topicsHeading')}
          </h2>
          <p className="text-[15px] text-muted-foreground">{t('home.topicsIntro')}</p>
        </div>
        <ul className="grid grid-cols-[repeat(auto-fit,minmax(min(280px,100%),1fr))] gap-5">
          {TOPIC_IDS.map((id) => (
            <li key={id}>
              <Link
                to={`/topics/${id}`}
                className="flex h-full flex-col gap-2 rounded-2xl border border-line bg-white p-6 text-navy no-underline transition-shadow hover:shadow-lg"
              >
                <span className="text-[13px] font-semibold text-muted-foreground">
                  {t(`topics.${id}.grade`)}
                </span>
                <span className="font-heading text-xl font-semibold">
                  {t(`topics.${id}.title`)}
                </span>
                <span className="mt-auto inline-flex items-center gap-2 pt-2 text-[15px] font-semibold">
                  {t('home.openTopic')}
                  <ArrowRight aria-hidden="true" className="size-4 rtl:-scale-x-100" />
                </span>
              </Link>
            </li>
          ))}
        </ul>
      </section>

      <section aria-labelledby="ways-heading" className="flex flex-col gap-4">
        <h2 id="ways-heading" className="sr-only">
          {t('home.waysHeading')}
        </h2>
        <ul className="grid grid-cols-[repeat(auto-fit,minmax(min(260px,100%),1fr))] gap-4">
          {ways.map(({ to, icon: Icon, title, text }) => (
            <li key={to}>
              <Link
                to={to}
                className="flex h-full gap-4 rounded-2xl border border-line bg-white p-5 text-navy no-underline transition-shadow hover:shadow-lg"
              >
                <span className="flex size-11 flex-none items-center justify-center rounded-xl bg-paleblue">
                  <Icon aria-hidden="true" className="size-5" />
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
