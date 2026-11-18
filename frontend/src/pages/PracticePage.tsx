import { ArrowLeft, ArrowRight, ClipboardCheck } from 'lucide-react'
import { useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useParams } from 'react-router'
import { isNotFound, useCheckWorking, usePack } from '@/api/queries'
import type { Pack, PracticeItem } from '@/api/types'
import { MathInput, type ConfirmedLines, type MathInputHandle } from '@/components/input'
import { LoadError, Loading } from '@/components/LoadState'
import { MathExpr } from '@/components/math'
import { CheckResult } from '@/components/practice/CheckResult'
import { HintLadder } from '@/components/practice/HintLadder'
import { RichText } from '@/components/RichText'
import { usePageTitle } from '@/components/shell/hooks'
import { Button } from '@/components/ui/button'
import { isTopicId, problemNumber } from '@/content/topics'
import { NotFoundPage } from '@/pages/NotFoundPage'
import { PageFrame } from '@/pages/PageFrame'

export function PracticePage() {
  const { topic, n } = useParams()
  const number = problemNumber(n)
  if (!isTopicId(topic) || number === null) return <NotFoundPage />
  return <PracticeLoader topic={topic} n={number} />
}

function PracticeLoader({ topic, n }: { topic: string; n: number }) {
  const { t } = useTranslation()
  const pack = usePack(topic)
  if (pack.isError && isNotFound(pack.error)) return <NotFoundPage />
  if (pack.isPending || pack.isError) {
    return (
      <PageFrame title={t('pages.practiceTitle', { topic: t(`topics.${topic}.title`) })}>
        {pack.isPending ? (
          <Loading />
        ) : (
          <LoadError error={pack.error} onRetry={() => void pack.refetch()} />
        )}
      </PageFrame>
    )
  }
  const item = pack.data.practice[n - 1]
  if (!item) return <NotFoundPage />
  // Keyed by problem: moving on forgets the working, the check and the open hints.
  return <Practice key={item.id} pack={pack.data} item={item} n={n} />
}

const stepLink =
  'inline-flex min-h-11 items-center gap-2 rounded-xl border border-line bg-white px-4 font-semibold text-navy no-underline hover:border-line-strong hover:bg-[#eef1f4]'

function Practice({ pack, item, n }: { pack: Pack; item: PracticeItem; n: number }) {
  const { t } = useTranslation()
  const total = pack.practice.length
  const title = t('pages.practiceTitle', { topic: pack.title })
  const problem = t('pages.practiceProblem', { n, total })
  usePageTitle(t('pages.practicePageTitle', { title, problem }))

  const input = useRef<MathInputHandle>(null)
  const [working, setWorking] = useState<ConfirmedLines | null>(null)
  const [error, setError] = useState<string>()
  const check = useCheckWorking()

  const onCheck = () => {
    if (!working) {
      setError(t('practice.needWorking'))
      input.current?.focus()
      return
    }
    setError(undefined)
    check.mutate({
      problem: { kind: item.problem.kind, text: item.problem.expr },
      lines: working.lines,
    })
  }

  return (
    <div className="mx-auto flex max-w-[1200px] flex-col gap-6 px-4 py-6 sm:px-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Link
          to={`/topics/${pack.topic}`}
          className="-ms-3 inline-flex min-h-11 items-center gap-2 rounded-[10px] px-3 font-medium text-[#3a4458] no-underline hover:bg-[#eef1f4]"
        >
          <ArrowLeft aria-hidden="true" className="size-[18px] rtl:-scale-x-100" />
          {t('practice.backToTopic', { topic: pack.title })}
        </Link>
        <span className="text-sm text-muted-foreground">{t('practice.header', { n, total })}</span>
      </div>

      <h1 className="text-3xl font-bold tracking-tight sm:text-4xl">{title}</h1>

      <div className="flex flex-wrap items-start gap-6">
        <div className="flex min-w-0 flex-[2_1_480px] flex-col gap-5">
          <section
            aria-labelledby="problem-heading"
            className="flex flex-col gap-4 rounded-[20px] border border-line bg-white p-5 sm:p-6"
          >
            <h2 id="problem-heading" className="text-sm font-semibold text-muted-foreground">
              {problem}
            </h2>
            <p className="flex flex-wrap items-center gap-3 text-lg font-semibold">
              <RichText text={item.prompt} />
              <MathExpr expr={item.problem.expr} className="text-3xl font-normal text-ink" />
            </p>
            <MathInput
              ref={input}
              shape="lines"
              defaultMode="write"
              label={t('practice.workingLabel')}
              description={t('practice.workingHint')}
              error={error}
              onChange={(v) => {
                // A verdict describes the working that was checked; once it changes, drop it.
                if (!check.isIdle) check.reset()
                setWorking(v)
                if (v) setError(undefined)
              }}
            />
            <Button className="min-h-11 self-start" onClick={onCheck} disabled={check.isPending}>
              <ClipboardCheck aria-hidden="true" />
              {check.isPending ? t('practice.checking') : t('practice.check')}
            </Button>
            <div aria-live="polite">
              {check.isError && <LoadError error={check.error} onRetry={onCheck} />}
              {check.data && <CheckResult result={check.data} />}
            </div>
          </section>

          <nav aria-label={t('pages.practiceNav')} className="flex flex-wrap justify-between gap-3">
            {n > 1 ? (
              <Link to={`/practice/${pack.topic}/${n - 1}`} className={stepLink}>
                <ArrowLeft aria-hidden="true" className="size-4 rtl:-scale-x-100" />
                {t('pages.previous')}
              </Link>
            ) : (
              <span />
            )}
            {n < total && (
              <Link to={`/practice/${pack.topic}/${n + 1}`} className={stepLink}>
                {t('pages.next')}
                <ArrowRight aria-hidden="true" className="size-4 rtl:-scale-x-100" />
              </Link>
            )}
          </nav>

          <p className="text-sm text-muted-foreground [overflow-wrap:anywhere]">
            {t('practice.sourceLabel')}{' '}
            <a
              href={item.source.url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-link-ink underline underline-offset-2"
            >
              {item.source.oer}
              <span className="sr-only"> {t('common.newTab')}</span>
            </a>{' '}
            · {item.license.replaceAll('-', ' ')}
          </p>
        </div>
        <div className="min-w-0 flex-[1_1_300px]">
          <HintLadder item={item} topic={pack.topic} />
        </div>
      </div>
    </div>
  )
}
