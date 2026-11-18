import type { ReactNode } from 'react'
import { useApiLang } from '@/api/queries'
import { ContentLangContext } from '@/components/content-lang'
import { findLanguage } from '@/i18n/languages'

/**
 * Marks the pack or diagnosis text inside (RichText and other `useContentLang` readers) with
 * `lang`, when it differs from the UI's. UI labels inside are not marked (WCAG 3.1.2).
 */
export function InLang({ lang, children }: { lang?: string | null; children: ReactNode }) {
  const ui = useApiLang()
  const value = lang && lang !== ui ? { lang, dir: findLanguage(lang).dir } : null
  return <ContentLangContext value={value}>{children}</ContentLangContext>
}
