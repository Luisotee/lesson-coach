import { useEffect, useRef } from 'react'
import { useTranslation } from 'react-i18next'
import { useLocation } from 'react-router'

/** Sets the document title to "<page> · Lesson Coach" in the active language (WCAG 2.4.2). */
export function usePageTitle(page?: string): void {
  const { t } = useTranslation()
  const title = page ? t('app.pageTitle', { page }) : t('app.title')
  useEffect(() => {
    document.title = title
  }, [title])
}

/**
 * After a client-side navigation, moves focus to the link's #target or to the page's <h1>, so
 * keyboard and screen-reader users start on the new page instead of the old link.
 * The first load keeps the browser's own focus.
 */
export function useRouteFocus(): void {
  const { pathname, hash } = useLocation()
  const firstLoad = useRef(true)
  useEffect(() => {
    if (firstLoad.current) {
      firstLoad.current = false
      return
    }
    const target = hash
      ? document.getElementById(decodeURIComponent(hash.slice(1)))
      : document.querySelector<HTMLElement>('main h1')
    if (!target) return
    if (!target.hasAttribute('tabindex')) target.setAttribute('tabindex', '-1')
    target.focus()
  }, [pathname, hash])
}
