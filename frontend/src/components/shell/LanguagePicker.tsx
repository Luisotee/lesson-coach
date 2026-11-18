import { Languages } from 'lucide-react'
import { useId } from 'react'
import { useTranslation } from 'react-i18next'
import { LANGUAGES, findLanguage } from '@/i18n/languages'

/** A native select: it works the same with keyboard, touch and screen readers everywhere. */
export function LanguagePicker() {
  const { t, i18n } = useTranslation()
  const id = useId()
  const current = findLanguage(i18n.resolvedLanguage ?? i18n.language).code
  return (
    <div className="flex items-center gap-2">
      <Languages aria-hidden="true" className="size-5 text-navy" />
      <label htmlFor={id} className="sr-only">
        {t('language.label')}
      </label>
      <select
        id={id}
        value={current}
        onChange={(e) => void i18n.changeLanguage(e.target.value)}
        className="min-h-11 rounded-lg border border-input bg-white ps-3 pe-8 text-sm font-medium text-navy"
      >
        {LANGUAGES.map((l) => (
          <option key={l.code} value={l.code} lang={l.code}>
            {l.status === 'machine' ? t('language.machine', { name: l.nativeName }) : l.nativeName}
          </option>
        ))}
      </select>
    </div>
  )
}
