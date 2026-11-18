import { useTranslation } from 'react-i18next'
import { Link } from 'react-router'
import { usePageTitle } from '@/components/shell/hooks'
import { PageFrame } from '@/pages/PageFrame'

export function NotFoundPage() {
  const { t } = useTranslation()
  usePageTitle(t('notFound.title'))
  return (
    <PageFrame title={t('notFound.title')}>
      <p className="text-lg text-muted-foreground">{t('notFound.body')}</p>
      <Link to="/" className="self-start font-semibold text-link-ink underline">
        {t('notFound.home')}
      </Link>
    </PageFrame>
  )
}
