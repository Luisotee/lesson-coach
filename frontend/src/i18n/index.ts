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
    fallbackLng: DEFAULT_LANGUAGE,
    supportedLngs: LANGUAGES.map((l) => l.code),
    nonExplicitSupportedLngs: true,
    load: 'languageOnly',
    interpolation: { escapeValue: false },
    // The choice is a UI preference kept only in this browser; no personal data.
    detection: {
      order: ['querystring', 'localStorage', 'navigator'],
      lookupQuerystring: 'lng',
      lookupLocalStorage: 'lesson-coach-lang',
      caches: ['localStorage'],
    },
    react: { useSuspense: true },
  })

export default i18n
