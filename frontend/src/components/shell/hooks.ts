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

/** The element a #hash names. A malformed escape is looked up as written instead of throwing. */
function hashTarget(hash: string): HTMLElement | null {
  let id = hash.slice(1)
  try {
    id = decodeURIComponent(id)
  } catch {
    // keep the raw id
  }
  return document.getElementById(id)
}

/**
 * After a client-side navigation, moves focus to the link's #target or to the page's <h1>, so
 * keyboard and screen-reader users start on the new page instead of the old link.
 * The first load keeps the browser's own focus (also under StrictMode's effect re-run), and
 * focusing never scrolls: ScrollRestoration owns the scroll position, including on Back.
 */
export function useRouteFocus(): void {
  const { key, hash } = useLocation()
  const initialKey = useRef(key)
  const navigated = useRef(false)
  useEffect(() => {
    if (!navigated.current && key === initialKey.current) return
    navigated.current = true
    // An unknown #target falls back to the page heading, so focus never stays on a stale link.
    const target = (hash && hashTarget(hash)) || document.querySelector<HTMLElement>('main h1')
    if (!target) return
    const focus = (el: HTMLElement) => {
      if (!el.hasAttribute('tabindex')) el.setAttribute('tabindex', '-1')
      el.focus({ preventScroll: true })
    }
    focus(target)
    if (hash) return
    // A page that loads its content replaces its loading heading: follow it to the new <h1>,
    // unless the user has already moved focus elsewhere.
    let current = target
    const main = document.querySelector('main')
    if (!main) return
    const observer = new MutationObserver(() => {
      if (current.isConnected) return
      if (document.activeElement && document.activeElement !== document.body) return
      const h1 = document.querySelector<HTMLElement>('main h1')
      if (h1) {
        current = h1
        focus(h1)
      }
    })
    observer.observe(main, { childList: true, subtree: true })
    const stop = window.setTimeout(() => observer.disconnect(), 10_000)
    return () => {
      observer.disconnect()
      window.clearTimeout(stop)
    }
  }, [key, hash])
}
