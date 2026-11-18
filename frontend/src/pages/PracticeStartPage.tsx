import { useTranslation } from 'react-i18next'
import { Navigate } from 'react-router'
import { usePacks, useTopics } from '@/api/queries'
import { LoadError, Loading } from '@/components/LoadState'
import { PageFrame } from '@/pages/PageFrame'

/**
 * Where "Practice" leads: the first problem of the first topic, in the API's order, that has
 * practice problems. Packs may ship without any, so no topic is assumed.
 */
export function PracticeStartPage() {
  const { t } = useTranslation()
  const topics = useTopics()
  const packs = usePacks(topics.data?.map((x) => x.id) ?? [])
  const firstIndex = packs.findIndex((p) => (p.data?.practice.length ?? 0) > 0)
  const first = packs[firstIndex]?.data
  // Packs answer in any order: wait for every earlier one, so the first in order wins.
  const earlierPending = packs.slice(0, firstIndex).some((p) => p.isPending)
  if (first && !earlierPending) return <Navigate replace to={`/practice/${first.topic}/1`} />

  const failed = topics.isError ? topics : packs.find((p) => p.isError)
  const pending = topics.isPending || packs.some((p) => p.isPending)
  return (
    <PageFrame title={t('nav.practice')}>
      {failed ? (
        <LoadError error={failed.error} onRetry={() => void failed.refetch()} />
      ) : pending ? (
        <Loading lines={3} />
      ) : (
        <p className="text-lg text-muted-foreground">{t('practice.noneYet')}</p>
      )}
    </PageFrame>
  )
}
