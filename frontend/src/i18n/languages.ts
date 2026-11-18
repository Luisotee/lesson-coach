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

/** Every language the app offers. A language listed here must have a complete locale file. */
export const LANGUAGES: readonly Language[] = [
  { code: 'en', nativeName: 'English', dir: 'ltr', script: 'latin', status: 'reviewed' },
  { code: 'ar', nativeName: 'العربية', dir: 'rtl', script: 'arabic', status: 'machine' },
]

export const DEFAULT_LANGUAGE = 'en'

export function findLanguage(code: string | undefined): Language {
  const base = code?.split('-')[0]
  return (
    LANGUAGES.find((l) => l.code === code) ??
    LANGUAGES.find((l) => l.code === base) ??
    LANGUAGES.find((l) => l.code === DEFAULT_LANGUAGE)!
  )
}
