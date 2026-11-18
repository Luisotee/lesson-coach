import { useEffect, useRef, type RefObject } from 'react'
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
 * Calls `check` on every change inside <main> for up to 10 s, until it returns true.
 * Returns the cleanup.
 */
function watchMain(check: () => boolean): (() => void) | undefined {
  const main = document.querySelector('main')
  if (!main) return
  const observer = new MutationObserver(() => {
    if (check()) observer.disconnect()
  })
  observer.observe(main, { childList: true, subtree: true })
  const stop = window.setTimeout(() => observer.disconnect(), 10_000)
  return () => {
    observer.disconnect()
    window.clearTimeout(stop)
  }
}

/**
 * After a client-side navigation, moves focus to the link's #target or to the page's <h1>, so
 * keyboard and screen-reader users start on the new page instead of the old link.
 * The first load keeps the browser's own focus (also under StrictMode's effect re-run), and
 * focusing never scrolls: ScrollRestoration owns the scroll position, including on Back.
 * A #target that a loading page adds later is scrolled into view once it appears, also on
 * the first load, since neither the browser nor ScrollRestoration found it in time.
 */
export function useRouteFocus(): void {
  const { key, hash } = useLocation()
  const initialKey = useRef(key)
  const navigated = useRef(false)
  useEffect(() => {
    if (!navigated.current && key === initialKey.current) {
      if (!hash || hashTarget(hash)) return
      return watchMain(() => {
        const target = hashTarget(hash)
        target?.scrollIntoView?.()
        return target !== null
      })
    }
    navigated.current = true
    const focus = (el: HTMLElement) => {
      if (!el.hasAttribute('tabindex')) el.setAttribute('tabindex', '-1')
      el.focus({ preventScroll: true })
    }
    const found = hash ? hashTarget(hash) : null
    if (found) {
      focus(found)
      return
    }
    // Until the page has its content (an unknown #target, or a page still loading), focus the
    // page heading, so focus never stays on a stale link.
    let current = document.querySelector<HTMLElement>('main h1')
    if (current) focus(current)
    // A page that loads its content replaces its loading heading. Follow it: to the #target
    // once it exists (scrolled into view, since ScrollRestoration found nothing to scroll to),
    // otherwise to the new <h1>. Not if the user has already moved focus elsewhere.
    return watchMain(() => {
      const active = document.activeElement
      if (active && active !== document.body && active !== current) return true
      const target = hash ? hashTarget(hash) : null
      if (target) {
        focus(target)
        target.scrollIntoView?.()
        return true
      }
      if (current?.isConnected) return false
      const h1 = document.querySelector<HTMLElement>('main h1')
      if (h1) {
        current = h1
        focus(h1)
      }
      return false
    })
  }, [key, hash])
}

/**
 * Keeps `--header-h` on <html> at the height the header covers while scrolling, so
 * `scroll-padding-top` stops anything scrolled into view (a focused element, a #section) below
 * it instead of under it (WCAG 2.4.11). That is its height while it is sticky (it grows as it
 * wraps), and 0 when it scrolls away with the page (on narrow or short windows, see index.css).
 */
export function useHeaderHeight(header: RefObject<HTMLElement | null>): void {
  useEffect(() => {
    const el = header.current
    if (!el || typeof ResizeObserver === 'undefined') return
    const root = document.documentElement
    const update = () => {
      const sticky = getComputedStyle(el).position === 'sticky'
      root.style.setProperty('--header-h', `${sticky ? el.offsetHeight : 0}px`)
    }
    // The header can stop being sticky without changing size (a window made shorter).
    const observer = new ResizeObserver(update)
    observer.observe(el)
    window.addEventListener('resize', update)
    return () => {
      observer.disconnect()
      window.removeEventListener('resize', update)
      root.style.removeProperty('--header-h')
    }
  }, [header])
}
