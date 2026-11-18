import { IntlMessageFormat } from 'intl-messageformat'
import { afterEach, describe, expect, test } from 'vitest'
import i18n from '@/i18n'
import { CANDIDATES, LANGUAGES, findLanguage } from '@/i18n/languages'
import en from '@/locales/en.json'
import { speakLine, speakText } from '@/math/speech'
import packStats from '../../../evals/translation-stats.json'
import uiStats from '../../../evals/translation-ui-stats.json'

/**
 * Every listed language's locale file is a faithful ICU twin of en.json: each message compiles
 * for its locale with the same arguments, and the spoken math is all in that language.
 * (pipeline/icu_check.mjs runs the same checks before a file is written.)
 */

type Messages = { [key: string]: string | Messages }

const files = import.meta.glob<Messages>('../locales/*.json', { eager: true, import: 'default' })
const locale = (code: string): Messages => files[`../locales/${code}.json`]

function flat(obj: Messages, prefix = ''): Record<string, string> {
  return Object.fromEntries(
    Object.entries(obj).flatMap(([k, v]) =>
      typeof v === 'string' ? [[`${prefix}${k}`, v]] : Object.entries(flat(v, `${prefix}${k}.`)),
    ),
  )
}

// The AST shapes of intl-messageformat: 1 argument, 2 number, 5 select, 6 plural, 8 tag.
type El = {
  type: number
  value?: string
  options?: Record<string, { value: El[] }>
  children?: El[]
}

function argumentsOf(ast: El[], found = new Set<string>()): Set<string> {
  for (const el of ast) {
    if ([1, 2, 5, 6].includes(el.type) && el.value) found.add(el.value)
    for (const option of Object.values(el.options ?? {})) argumentsOf(option.value, found)
    if (el.children) argumentsOf(el.children, found)
  }
  return found
}

const english = flat(en as Messages)
const translated = LANGUAGES.filter((l) => l.code !== 'en')
const intlLocale = (code: string) => (code === 'prs' ? 'fa-AF' : code)

afterEach(() => i18n.changeLanguage('en'))

test('the listed languages are exactly those whose packs and UI strings both shipped', () => {
  type Run = Record<string, { shipped: boolean }>
  const shipped = (stats: Run) => Object.keys(stats).filter((code) => stats[code].shipped)
  const both = shipped(packStats as Run).filter((code) => shipped(uiStats as Run).includes(code))
  expect(LANGUAGES.map((l) => l.code).sort()).toEqual(['en', ...both].sort())
})

test('every listed language is a candidate, and right-to-left exactly for the RTL scripts', () => {
  for (const l of LANGUAGES) {
    expect(CANDIDATES).toContainEqual(l)
    expect(l.dir, l.code).toBe(['ar', 'fa', 'ur', 'ps', 'prs'].includes(l.code) ? 'rtl' : 'ltr')
  }
})

describe.each(translated.map((l) => [l.code]))('%s', (code) => {
  const messages = flat(locale(code))

  test('every message compiles for its locale with the English arguments', () => {
    for (const [key, text] of Object.entries(english)) {
      const want = [...argumentsOf(new IntlMessageFormat(text, 'en').getAst() as El[])].sort()
      const ast = new IntlMessageFormat(messages[key], intlLocale(code)).getAst() as El[]
      expect([...argumentsOf(ast)].sort(), `${code} ${key}`).toEqual(want)
    }
  })

  test('plural messages give a word for every count', async () => {
    await i18n.loadLanguages(code) // else t() would fall back to English
    expect(i18n.hasResourceBundle(code, 'translation')).toBe(true)
    const t = i18n.getFixedT(code)
    for (const count of [0, 1, 2, 3, 5, 11, 21, 100]) {
      for (const key of ['input.write.strokes', 'input.review.toCheck', 'mistake.possibilities']) {
        const said = t(key, { count })
        expect(said, `${code} ${key} ${count}`).not.toMatch(/[{}]/)
        expect(said).not.toBe(key)
      }
    }
  })

  test('a spoken fraction says its own numbers, in ASCII or local digits', async () => {
    await i18n.loadLanguages(code)
    const t = i18n.getFixedT(code)
    const digits = new Intl.NumberFormat(intlLocale(code))
    const says = (text: string, n: number) =>
      [String(n), digits.format(n)].some((form) =>
        new RegExp(`(^|[^\\p{Nd}])${form}($|[^\\p{Nd}])`, 'u').test(text),
      )
    const read = (num: number, den: number) => t('math.speech.fractionSimple', { num, den })
    // A CLDR category is not a number: French `one` is also 0, Russian `one` is also 21.
    expect(says(read(0, 3), 0), `${code} 0/3: ${read(0, 3)}`).toBe(true)
    expect(says(read(21, 4), 21), `${code} 21/4: ${read(21, 4)}`).toBe(true)
    expect(read(1, 3), `${code} 1/3`).not.toBe(read(0, 3))
    expect(read(1, 3)).not.toMatch(/[{}]/)
  })

  test('spoken math is all in the language, with no placeholder left', async () => {
    await i18n.loadLanguages(code)
    const t = i18n.getFixedT(code)
    const lines = [
      speakText('1/2 + 1/3', t),
      speakText('2*(x + 3) = -(4/7)', t),
      speakText('(-3)**2 - 2**(x + 1) + x**3', t),
      speakText('(1+1)/(2+3)', t),
      speakLine({ left: '2*x + 6', right: '10', op: '-6' }, t),
      speakLine({ left: '2*x', right: '4', op: '/2' }, t),
      speakLine({ left: '3*x', right: '', op: '*3', continued: true }, t),
    ]
    for (const [i, said] of lines.entries()) {
      expect(said, `${code} line ${i}`).not.toMatch(/[{}]/)
    }
    // Every spoken phrase comes from the language's own file, never the English fallback.
    for (const key of Object.keys(english).filter((k) => /^math\.(speech|op)\./.test(k))) {
      expect(i18n.exists(key, { lng: code, fallbackLng: false }), `${code} ${key}`).toBe(true)
    }
  })
})

test('a code with a region loads its own file; an unknown region falls back to its language', async () => {
  for (const { code } of translated) {
    await i18n.changeLanguage(code)
    expect(document.documentElement).toHaveAttribute('lang', code)
    expect(i18n.t('nav.topics')).toBe(flat(locale(code))['nav.topics'])
  }
  await i18n.changeLanguage('ar-EG')
  expect(i18n.t('nav.topics')).toBe(flat(locale('ar'))['nav.topics'])
  if (findLanguage('zh-CN').code === 'zh-Hans') {
    await i18n.changeLanguage('zh-CN')
    expect(document.documentElement).toHaveAttribute('lang', 'zh-Hans')
  }
})

test('codes are matched ignoring case, and every Chinese gets the one Chinese listed', () => {
  expect(findLanguage('pt-br').code).toBe('pt-BR')
  expect(findLanguage('PT').code).toBe('pt')
  expect(findLanguage('ar-EG').code).toBe('ar')
  expect(findLanguage('xx-YY').code).toBe('en')
  expect(findLanguage(undefined).code).toBe('en')
  for (const code of ['zh', 'zh-CN', 'zh-Hant', 'zh-TW', 'zh-HK', 'zh-Hant-TW', 'ZH-hans']) {
    expect(findLanguage(code).code, code).toBe('zh-Hans')
  }
})
