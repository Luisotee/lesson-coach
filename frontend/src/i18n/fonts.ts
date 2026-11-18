import type { Script } from '@/i18n/languages'

/**
 * Font files per writing system, loaded only when a language that uses it becomes active.
 * Inter covers Latin, Cyrillic (including Kazakh) and Greek; Kalam covers Latin and Devanagari,
 * and the math itself is ASCII, so Kalam always draws it. CJK (zh-Hans) is added with that
 * language in T9: its font is about 4.6 MB of subsets in the build.
 */
const loaders: Partial<Record<Script, () => Promise<unknown>>> = {
  arabic: () => import('@fontsource-variable/noto-sans-arabic'),
  devanagari: () => import('@fontsource-variable/noto-sans-devanagari'),
  bengali: () => import('@fontsource-variable/noto-sans-bengali'),
  ethiopic: () => import('@fontsource-variable/noto-sans-ethiopic'),
}

const loaded = new Set<Script>()

export function loadScriptFont(script: Script): void {
  const load = loaders[script]
  if (!load || loaded.has(script)) return
  loaded.add(script)
  // A missing font only means the system fallback is used; the text stays readable.
  load().catch(() => loaded.delete(script))
}
