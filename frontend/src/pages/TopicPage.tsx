import { useTranslation } from 'react-i18next'
import { useParams } from 'react-router'
import { usePageTitle } from '@/components/shell/hooks'
import { isTopicId } from '@/content/topics'
import { NotFoundPage } from '@/pages/NotFoundPage'
import { PageFrame } from '@/pages/PageFrame'

/** Placeholder until T8 renders the topic pack. */
export function TopicPage() {
  const { id } = useParams()
  if (!isTopicId(id)) return <NotFoundPage />
  return <KnownTopic id={id} />
}

function KnownTopic({ id }: { id: string }) {
  const { t } = useTranslation()
  const title = t(`topics.${id}.title`)
  usePageTitle(title)
  return (
    <PageFrame title={title}>
      <p className="max-w-2xl text-lg text-muted-foreground">{t('pages.inProgress')}</p>
    </PageFrame>
  )
}
