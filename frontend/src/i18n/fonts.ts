import type { Script } from '@/i18n/languages'

/**
 * Font files per writing system, loaded only when a language that uses it becomes active.
 * Inter covers Latin, Cyrillic (including Kazakh) and Greek for the interface. The handwriting
 * face is Kalam (Latin and Devanagari); Kalam has no Cyrillic or Greek, so those scripts get
 * Playpen Sans (OFL, a handwriting face with both). Arabic, Bengali, Ethiopic and CJK use the
 * Noto families for both. The math itself is ASCII, so Kalam always draws it. The CJK font is
 * about 4.6 MB of unicode-range subsets; the browser fetches only the subsets a page uses.
 */
const loaders: Partial<Record<Script, () => Promise<unknown>>> = {
  arabic: () => import('@fontsource-variable/noto-sans-arabic'),
  devanagari: () => import('@fontsource-variable/noto-sans-devanagari'),
  bengali: () => import('@fontsource-variable/noto-sans-bengali'),
  ethiopic: () => import('@fontsource-variable/noto-sans-ethiopic'),
  hans: () => import('@fontsource-variable/noto-sans-sc'),
  cyrillic: () => import('@fontsource-variable/playpen-sans'),
  greek: () => import('@fontsource-variable/playpen-sans'),
}

const loaded = new Set<Script>()

export function loadScriptFont(script: Script): void {
  const load = loaders[script]
  if (!load || loaded.has(script)) return
  loaded.add(script)
  // A missing font only means the system fallback is used; the text stays readable.
  load().catch(() => loaded.delete(script))
}
