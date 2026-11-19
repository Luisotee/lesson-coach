/**
 * Smooth scrolling for moves within a page, never for page changes.
 *
 * A global `scroll-behavior: smooth` would also animate React Router's scroll to the top on
 * every new page and its restore on Back. So `html.smooth-scroll` (index.css) is set only around
 * a move inside the page: a same-page #link, or a focus or scrollIntoView after a button. Every
 * scroll the browser makes then (React Router's scrollIntoView for a #hash, focus() bringing an
 * element into view) animates, and still stops below the sticky header (scroll-padding-top).
 * Under prefers-reduced-motion the class does nothing and scrolling stays instant.
 */
const CLASS = 'smooth-scroll'
let off: (() => void) | undefined

export function reducedMotion(): boolean {
  return window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false
}

/** Runs `move` (if any) with smooth scrolling on, and turns it off once the scroll ends. */
export function smoothly(move?: () => void): void {
  const root = document.documentElement
  if (!reducedMotion()) {
    off?.()
    root.classList.add(CLASS)
    // A move that needs no scroll fires no scrollend: the timer turns it off then.
    const timer = window.setTimeout(() => off?.(), 1500)
    const end = () => off?.()
    off = () => {
      root.classList.remove(CLASS)
      window.clearTimeout(timer)
      window.removeEventListener('scrollend', end)
      off = undefined
    }
    // Added after this task, so a scroll already ending doesn't turn it off at once.
    window.setTimeout(() => off && window.addEventListener('scrollend', end, { once: true }))
  }
  move?.()
}

/**
 * Scrolls with `move` (smoothly, see `smoothly`), then runs `then` once the scroll has ended:
 * at once under reduced motion, where the scroll is instant.
 */
export function smoothlyThen(move: () => void, then: () => void): void {
  if (reducedMotion()) {
    move()
    then()
    return
  }
  let done = false
  const finish = () => {
    if (done) return
    done = true
    window.removeEventListener('scrollend', finish)
    window.clearTimeout(timer)
    then()
  }
  const timer = window.setTimeout(finish, 1000)
  // Added after this task, as in `smoothly`: a scroll already ending must not count as ours.
  window.setTimeout(() => !done && window.addEventListener('scrollend', finish))
  smoothly(move)
}

/** Whether a click on `a` is a plain same-page jump to a #target (not a new tab or page). */
export function isSamePageHashClick(e: MouseEvent, a: HTMLAnchorElement): boolean {
  if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey)
    return false
  if (a.target && a.target !== '_self') return false
  const url = new URL(a.href, window.location.href)
  return (
    url.hash.length > 1 &&
    url.origin === window.location.origin &&
    url.pathname === window.location.pathname &&
    url.search === window.location.search
  )
}
