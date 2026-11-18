import { useTranslation } from 'react-i18next'

/** "Grade 7–8" from a pack's grade list; nothing until the content has grades. */
export function useGradeLabel(grades: number[] | undefined): string | null {
  const { t } = useTranslation()
  if (!grades?.length) return null
  const from = Math.min(...grades)
  const to = Math.max(...grades)
  return from === to ? t('common.grade', { grade: from }) : t('common.grades', { from, to })
}
