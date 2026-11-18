import { createContext, useContext } from 'react'

/** The language of pack text when it differs from the UI's (a pack served in English). */
export const ContentLangContext = createContext<{ lang: string; dir: 'ltr' | 'rtl' } | null>(null)

/**
 * `lang`/`dir` for an element that holds pack text, or nothing when the pack is in the UI
 * language. Only pack text is marked, so UI labels around it keep the UI language (WCAG 3.1.2).
 */
export function useContentLang(): { lang?: string; dir?: 'ltr' | 'rtl' } {
  return useContext(ContentLangContext) ?? {}
}
