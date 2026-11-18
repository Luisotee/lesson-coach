/** Writing systems that need their own font files (see fonts.ts). Latin, Cyrillic and Greek need none. */
export type Script =
  'latin' | 'cyrillic' | 'greek' | 'arabic' | 'devanagari' | 'bengali' | 'ethiopic' | 'hans'

export interface Language {
  code: string
  /** The language's name in itself, shown in the picker. */
  nativeName: string
  dir: 'ltr' | 'rtl'
  script: Script
  /** `machine`: machine-translated and not yet reviewed; the picker says so. */
  status: 'reviewed' | 'machine'
}

const machine = (
  code: string,
  nativeName: string,
  script: Script,
  dir: 'ltr' | 'rtl' = 'ltr',
): Language => ({ code, nativeName, dir, script, status: 'machine' })

/** Every language the pipeline translates into (PLAN, "Languages"), in the PLAN's order. */
export const CANDIDATES: readonly Language[] = [
  { code: 'en', nativeName: 'English', dir: 'ltr', script: 'latin', status: 'reviewed' },
  machine('ar', 'العربية', 'arabic', 'rtl'),
  machine('fr', 'Français', 'latin'),
  machine('de', 'Deutsch', 'latin'),
  machine('el', 'Ελληνικά', 'greek'),
  machine('it', 'Italiano', 'latin'),
  machine('pt', 'Português', 'latin'),
  machine('pt-BR', 'Português (Brasil)', 'latin'),
  machine('ru', 'Русский', 'cyrillic'),
  machine('es', 'Español', 'latin'),
  machine('sv', 'Svenska', 'latin'),
  machine('pl', 'Polski', 'latin'),
  machine('kk', 'Қазақ тілі', 'cyrillic'),
  machine('uk', 'Українська', 'cyrillic'),
  machine('tr', 'Türkçe', 'latin'),
  machine('fa', 'فارسی', 'arabic', 'rtl'),
  machine('ur', 'اردو', 'arabic', 'rtl'),
  machine('hi', 'हिन्दी', 'devanagari'),
  machine('bn', 'বাংলা', 'bengali'),
  machine('zh-Hans', '简体中文', 'hans'),
  machine('sw', 'Kiswahili', 'latin'),
  machine('so', 'Soomaali', 'latin'),
  machine('ti', 'ትግርኛ', 'ethiopic'),
  machine('ps', 'پښتو', 'arabic', 'rtl'),
  machine('prs', 'دری', 'arabic', 'rtl'),
]

/**
 * The languages that passed every check (evals/translation-report.md): complete UI strings and
 * all packs. Only these are offered. Every one but English is machine-translated and unreviewed.
 */
const AVAILABLE = new Set([
  'en',
  'ar',
  'fr',
  'de',
  'el',
  'it',
  'pt',
  'pt-BR',
  'ru',
  'es',
  'sv',
  'pl',
  'kk',
  'tr',
  'fa',
  'ur',
  'hi',
  'bn',
  'zh-Hans',
])

/** Every language the app offers. A language listed here must have a complete locale file. */
export const LANGUAGES: readonly Language[] = CANDIDATES.filter((l) => AVAILABLE.has(l.code))

export const DEFAULT_LANGUAGE = 'en'

/**
 * Codes that read another listed language. Chinese in any script or region gets Simplified
 * Chinese, the one Chinese we have: closer than English for most readers of Traditional too.
 */
const ALIASES: Record<string, string> = {
  zh: 'zh-Hans',
  'zh-hant': 'zh-Hans',
  'zh-cn': 'zh-Hans',
  'zh-sg': 'zh-Hans',
  'zh-tw': 'zh-Hans',
  'zh-hk': 'zh-Hans',
  'zh-mo': 'zh-Hans',
}

/**
 * The listed language for a code such as `pt-br`, `ar-EG` or `zh-Hant-TW`, ignoring case: the
 * code itself, else shorter and shorter prefixes of it (`ar-EG` -> `ar`), each also looked up in
 * ALIASES; English when none is listed.
 */
export function findLanguage(code: string | undefined): Language {
  const parts = (code ?? '').toLowerCase().split('-')
  for (let n = parts.length; n > 0; n--) {
    const wanted = parts.slice(0, n).join('-')
    const target = ALIASES[wanted]?.toLowerCase() ?? wanted
    const found = LANGUAGES.find((l) => l.code.toLowerCase() === target)
    if (found) return found
  }
  return LANGUAGES.find((l) => l.code === DEFAULT_LANGUAGE)!
}
