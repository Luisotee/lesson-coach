import { ArrowLeft, ArrowRight } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Link, useParams } from 'react-router'
import { usePageTitle } from '@/components/shell/hooks'
import { PRACTICE_COUNT, isTopicId } from '@/content/topics'
import { NotFoundPage } from '@/pages/NotFoundPage'
import { PageFrame } from '@/pages/PageFrame'

/** Parses the 1-based problem number; anything else is not a page. */
function problemNumber(raw: string | undefined): number | null {
  if (!raw || !/^\d+$/.test(raw)) return null
  const n = Number(raw)
  return n >= 1 && n <= PRACTICE_COUNT ? n : null
}

/** Placeholder until T8 adds the problems and hints; previous and next already work. */
export function PracticePage() {
  const { topic, n } = useParams()
  const number = problemNumber(n)
  if (!isTopicId(topic) || number === null) return <NotFoundPage />
  return <Practice topic={topic} n={number} />
}

const stepLink =
  'inline-flex min-h-11 items-center gap-2 rounded-lg border border-line bg-white px-4 font-semibold text-navy no-underline hover:bg-[#eef1f4]'

function Practice({ topic, n }: { topic: string; n: number }) {
  const { t } = useTranslation()
  const title = t('pages.practiceTitle', { topic: t(`topics.${topic}.title`) })
  const problem = t('pages.practiceProblem', { n, total: PRACTICE_COUNT })
  usePageTitle(`${title}, ${problem}`)
  return (
    <PageFrame title={title}>
      <p className="text-lg font-semibold">{problem}</p>
      <p className="max-w-2xl text-lg text-muted-foreground">{t('pages.inProgress')}</p>
      <nav aria-label={t('pages.practiceNav')} className="flex flex-wrap gap-3">
        {n > 1 && (
          <Link to={`/practice/${topic}/${n - 1}`} className={stepLink}>
            <ArrowLeft aria-hidden="true" className="size-4 rtl:-scale-x-100" />
            {t('pages.previous')}
          </Link>
        )}
        {n < PRACTICE_COUNT && (
          <Link to={`/practice/${topic}/${n + 1}`} className={stepLink}>
            {t('pages.next')}
            <ArrowRight aria-hidden="true" className="size-4 rtl:-scale-x-100" />
          </Link>
        )}
      </nav>
    </PageFrame>
  )
}
