import { useCallback, useSyncExternalStore } from 'react'

/** Whether a media query matches now; updates when it changes. False where unsupported. */
export function useMediaQuery(query: string): boolean {
  // Stable per query, so the listener isn't removed and re-added on every render.
  const subscribe = useCallback(
    (onChange: () => void) => {
      if (typeof window.matchMedia !== 'function') return () => {}
      const mql = window.matchMedia(query)
      mql.addEventListener('change', onChange)
      return () => mql.removeEventListener('change', onChange)
    },
    [query],
  )
  return useSyncExternalStore(
    subscribe,
    () => typeof window.matchMedia === 'function' && window.matchMedia(query).matches,
  )
}

/** Below Tailwind's `md` (768 px): the phone layout. */
export const PHONE_QUERY = '(max-width: 767.98px)'
