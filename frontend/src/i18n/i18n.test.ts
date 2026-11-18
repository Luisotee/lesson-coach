import { afterEach, expect, test } from 'vitest'
import i18n from '@/i18n'
import { LANGUAGES } from '@/i18n/languages'
import ar from '@/locales/ar.json'
import en from '@/locales/en.json'

afterEach(() => i18n.changeLanguage('en'))

function keys(obj: object, prefix = ''): string[] {
  return Object.entries(obj).flatMap(([k, v]) =>
    typeof v === 'object' && v !== null ? keys(v, `${prefix}${k}.`) : [`${prefix}${k}`],
  )
}

test('changing the language sets lang and dir on <html>', async () => {
  await i18n.changeLanguage('ar')
  expect(document.documentElement).toHaveAttribute('lang', 'ar')
  expect(document.documentElement).toHaveAttribute('dir', 'rtl')
  expect(i18n.t('nav.topics')).toBe(ar.nav.topics)

  await i18n.changeLanguage('en')
  expect(document.documentElement).toHaveAttribute('lang', 'en')
  expect(document.documentElement).toHaveAttribute('dir', 'ltr')
})

test('a regional code falls back to its language', async () => {
  await i18n.changeLanguage('ar-EG')
  expect(document.documentElement).toHaveAttribute('lang', 'ar')
  expect(document.documentElement).toHaveAttribute('dir', 'rtl')
})

test('every listed language has a locale file with every English key', async () => {
  const files = import.meta.glob<object>('../locales/*.json', { eager: true, import: 'default' })
  const locales = Object.fromEntries(
    Object.entries(files).map(([path, data]) => [path.replace(/^.*\/|\.json$/g, ''), data]),
  )
  expect(Object.keys(locales).sort()).toEqual(LANGUAGES.map((l) => l.code).sort())
  for (const { code } of LANGUAGES) {
    expect(keys(locales[code]).sort(), code).toEqual(keys(en).sort())
  }
})
