import { useTranslation } from 'react-i18next'
import { usePageTitle } from '@/components/shell/hooks'
import { PageFrame } from '@/pages/PageFrame'

/** Placeholder until T7 and T8 add the input and result screens. */
export function MistakePage() {
  const { t } = useTranslation()
  const title = t('pages.mistakeTitle')
  usePageTitle(title)
  return (
    <PageFrame title={title}>
      <p className="max-w-2xl text-lg text-muted-foreground">{t('pages.inProgress')}</p>
    </PageFrame>
  )
}
