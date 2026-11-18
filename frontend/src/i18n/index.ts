import i18n from 'i18next'
import LanguageDetector from 'i18next-browser-languagedetector'
import ICU from 'i18next-icu'
import resourcesToBackend from 'i18next-resources-to-backend'
import { initReactI18next } from 'react-i18next'
import { loadScriptFont } from '@/i18n/fonts'
import { DEFAULT_LANGUAGE, LANGUAGES, findLanguage } from '@/i18n/languages'
import en from '@/locales/en.json'

// Every locale except English is its own chunk, fetched when that language is chosen.
const locales = import.meta.glob<{ default: Record<string, unknown> }>([
  '../locales/*.json',
  '!../locales/en.json',
])

/** Sets `lang` and `dir` on <html> and loads the script's font. Runs on init and every change. */
export function applyLanguage(code: string): void {
  const language = findLanguage(code)
  document.documentElement.lang = language.code
  document.documentElement.dir = language.dir
  loadScriptFont(language.script)
}

i18n.on('languageChanged', applyLanguage)

export const ready = i18n
  .use(ICU)
  .use(LanguageDetector)
  .use(
    resourcesToBackend(async (lng: string) => {
      const load = locales[`../locales/${lng}.json`]
      if (!load) throw new Error(`No locale file for ${lng}`)
      return (await load()).default
    }),
  )
  .use(initReactI18next)
  .init({
    resources: { en: { translation: en } },
    partialBundledLanguages: true,
    // Codes such as pt-BR and zh-Hans are languages of their own here, so each code loads its
    // own file; a regional code (de-AT, zh-CN) falls back to the listed language findLanguage
    // picks, then English.
    fallbackLng: (code: string) => [findLanguage(code).code, DEFAULT_LANGUAGE],
    // No nonExplicitSupportedLngs: it checks only the language part, so zh-Hans would be
    // judged by "zh", which isn't listed. Regional codes are mapped by findLanguage instead.
    supportedLngs: LANGUAGES.map((l) => l.code),
    load: 'currentOnly',
    interpolation: { escapeValue: false },
    // The choice is a UI preference kept only in this browser; no personal data.
    detection: {
      order: ['querystring', 'localStorage', 'navigator'],
      lookupQuerystring: 'lng',
      lookupLocalStorage: 'lesson-coach-lang',
      caches: ['localStorage'],
      convertDetectedLanguage: (code: string) => findLanguage(code).code,
    },
    react: { useSuspense: true },
  })

export default i18n
