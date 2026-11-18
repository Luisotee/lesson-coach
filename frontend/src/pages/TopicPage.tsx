import { ArrowLeft, Printer } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Link, useParams } from 'react-router'
import { isNotFound, usePack, useApiLang } from '@/api/queries'
import type { Pack } from '@/api/types'
import { useGradeLabel } from '@/components/Grades'
import { LoadError, Loading } from '@/components/LoadState'
import { usePageTitle } from '@/components/shell/hooks'
import { SectionNav, type Section } from '@/components/topic/SectionNav'
import {
  IdeaCards,
  LessonOutline,
  Misconceptions,
  RefreshFirst,
  StudentQuestions,
} from '@/components/topic/Sections'
import { WorkedExamples } from '@/components/topic/WorkedExamples'
import { Button } from '@/components/ui/button'
import { isTopicId } from '@/content/topics'
import { findLanguage } from '@/i18n/languages'
import { NotFoundPage } from '@/pages/NotFoundPage'
import { PageFrame } from '@/pages/PageFrame'

export function TopicPage() {
  const { id } = useParams()
  if (!isTopicId(id)) return <NotFoundPage />
  return <TopicLoader id={id} />
}

function TopicLoader({ id }: { id: string }) {
  const { t } = useTranslation()
  const pack = usePack(id)
  if (pack.isError && isNotFound(pack.error)) return <NotFoundPage />
  if (pack.isPending || pack.isError) {
    return (
      <PageFrame title={t(`topics.${id}.title`)}>
        {pack.isPending ? (
          <Loading lines={5} />
        ) : (
          <LoadError error={pack.error} onRetry={() => void pack.refetch()} />
        )}
      </PageFrame>
    )
  }
  return <TopicView pack={pack.data} />
}

function TopicView({ pack }: { pack: Pack }) {
  const { t } = useTranslation()
  const uiLang = useApiLang()
  const grade = useGradeLabel(pack.grades)
  usePageTitle(pack.title)
  // Content served in a fallback language is marked so screen readers switch voice.
  const fallback = pack.lang !== uiLang
  const contentLang = fallback ? { lang: pack.lang, dir: findLanguage(pack.lang).dir } : {}

  const sections: Section[] = [
    { id: 'idea', label: t('topic.sections.idea') },
    ...(pack.prerequisites.length ? [{ id: 'refresh', label: t('topic.sections.refresh') }] : []),
    { id: 'example', label: t('topic.sections.example') },
    { id: 'mistakes', label: t('topic.sections.mistakes') },
    ...(pack.questions.length ? [{ id: 'questions', label: t('topic.sections.questions') }] : []),
    ...(pack.outline.length ? [{ id: 'outline', label: t('topic.sections.outline') }] : []),
  ]

  return (
    <div className="mx-auto max-w-[1200px] px-4 pb-20 sm:px-6">
      <div className="flex flex-wrap items-center justify-between gap-3 py-3 print:hidden">
        <Link
          to={{ pathname: '/', hash: '#topics' }}
          className="-ms-3 inline-flex min-h-11 items-center gap-2 rounded-[10px] px-3 font-medium text-[#3a4458] no-underline hover:bg-[#eef1f4]"
        >
          <ArrowLeft aria-hidden="true" className="size-[18px] rtl:-scale-x-100" />
          {t('topic.allTopics')}
        </Link>
        {pack.outline.length > 0 && (
          <Button
            variant="outline"
            className="min-h-11 bg-white font-semibold"
            onClick={() => window.print()}
          >
            <Printer aria-hidden="true" />
            {t('topic.printOutline')}
          </Button>
        )}
      </div>

      <div className="flex flex-col gap-3 pt-4" {...contentLang}>
        <div className="flex flex-wrap gap-2 print:hidden">
          {grade && (
            <span className="rounded-full bg-paleblue/50 px-3 py-1.5 text-[13px] font-semibold text-link-ink">
              {grade}
            </span>
          )}
          {(pack.machine_translated || fallback) && (
            <span
              className="rounded-full border border-line bg-white px-3 py-1.5 text-[13px] text-muted-foreground"
              lang={uiLang}
            >
              {fallback ? t('topic.servedInEnglish') : t('common.machineTranslated')}
            </span>
          )}
        </div>
        <h1 className="text-[clamp(34px,4.4vw,52px)] leading-[1.05] font-bold tracking-[-0.03em]">
          {pack.title}
        </h1>
        {pack.summary && (
          <p className="max-w-[44rem] text-lg leading-relaxed text-muted-foreground print:hidden">
            {pack.summary}
          </p>
        )}
      </div>

      <div className="mt-9 flex flex-col gap-8 lg:flex-row lg:items-start">
        <SectionNav sections={sections} />
        <div className="flex min-w-0 flex-1 flex-col gap-7" {...contentLang}>
          <IdeaCards pack={pack} />
          {pack.prerequisites.length > 0 && <RefreshFirst ids={pack.prerequisites} />}
          <WorkedExamples examples={pack.worked_examples} />
          <Misconceptions items={pack.misconceptions} />
          {pack.questions.length > 0 && <StudentQuestions items={pack.questions} />}
          {pack.outline.length > 0 && <LessonOutline pack={pack} />}
        </div>
      </div>
    </div>
  )
}
