// Checks translated ICU messages against their English: the message compiles for its locale
// with intl-messageformat (what i18next-icu uses), has the same arguments, and every plural
// uses only the locale's CLDR categories (plus any `=N`), always with `other`, and all of them
// where the English names a category such as `one`, unless that plural has only `=N` branches
// and `other`. A plural's count must still be said where
// the English says it: a CLDR category covers more than one number (`one` is also 0 in French
// and 21 in Russian), so only an `=N` branch may put the number in words.
//
//   echo '{"locale": "ru", "items": {"key": ["English", "Русский"]}}' | node pipeline/icu_check.mjs
//
// Prints {key: [problem, ...]} for the items with problems. Run from the repo root; the
// library comes from frontend/node_modules.
import { createRequire } from 'node:module'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

const root = path.dirname(path.dirname(fileURLToPath(import.meta.url)))
const require = createRequire(path.join(root, 'frontend', 'package.json'))
const { IntlMessageFormat } = require('intl-messageformat')

const ARGUMENT = 1
const NUMBER = 2
const DATE = 3
const TIME = 4
const SELECT = 5
const PLURAL = 6
const TAG = 8

// Plural arguments whose English names categories (`one`), not only `=N` and `other`: only
// these must name every category of the target locale.
let named = new Set()

function walk(ast, found, locale, problems) {
  for (const el of ast) {
    if ([ARGUMENT, NUMBER, DATE, TIME].includes(el.type)) found.add(el.value)
    if (el.type === SELECT || el.type === PLURAL) {
      found.add(el.value)
      const keys = Object.keys(el.options)
      if (!keys.includes('other')) problems.add(`{${el.value}} needs an "other" branch`)
      if (el.type === PLURAL && !el.pluralType?.startsWith('ordinal')) {
        const wanted = new Intl.PluralRules(locale).resolvedOptions().pluralCategories
        const categories = keys.filter((k) => !k.startsWith('='))
        if (locale === 'en' && categories.some((k) => k !== 'other')) named.add(el.value)
        const extra = categories.filter((k) => !wanted.includes(k))
        // Where the English names categories for this argument, a plural needs them all,
        // unless it has only `=N` branches and `other` (`=1 {one} other {#}`).
        const exact = keys.some((k) => k.startsWith('='))
        const needsAll =
          named.has(el.value) && (categories.some((k) => k !== 'other') || !exact)
        const missing = needsAll ? wanted.filter((k) => !categories.includes(k)) : []
        if (extra.length) problems.add(`{${el.value}, plural}: ${extra} not used in ${locale}`)
        if (missing.length) problems.add(`{${el.value}, plural} needs ${missing} for ${locale}`)
      }
      for (const option of Object.values(el.options)) walk(option.value, found, locale, problems)
    }
    if (el.type === TAG) walk(el.children, found, locale, problems)
  }
}

// The arguments of a message and how each is used, to give it sample values.
function kinds(ast, found = {}) {
  for (const el of ast) {
    if (el.type === PLURAL || el.type === NUMBER) found[el.value] = 'number'
    else if (el.type === SELECT) found[el.value] ??= 'select'
    else if (el.type === ARGUMENT || el.type === DATE || el.type === TIME) found[el.value] ??= 'text'
    else if (el.type === TAG) found[el.value] = 'tag'
    for (const option of Object.values(el.options ?? {})) kinds(option.value, found)
    if (el.children) kinds(el.children, found)
  }
  return found
}

const SAMPLES = [0, 21, 101]

function saysNumber(text, n, locale) {
  const forms = new Set([String(n), new Intl.NumberFormat(locale).format(n)])
  return [...forms].some((form) => new RegExp(`(^|[^\\p{Nd}])${form}($|[^\\p{Nd}])`, 'u').test(text))
}

// A `zero` category that holds only 0 (Arabic) is as exact as `=0`: it may say "no lines".
function exactZero(locale) {
  const rules = new Intl.PluralRules(locale)
  return rules.select(0) === 'zero' && [10, 20, 100].every((n) => rules.select(n) !== 'zero')
}

// Each plural count from SAMPLES (the other numbers at 7): where the English says the count,
// the translation must say it too, in ASCII or the locale's digits.
function countProblems(english, translated, locale, problems) {
  const types = kinds(new IntlMessageFormat(english, 'en').getAst())
  const samples = exactZero(locale) ? SAMPLES.filter((n) => n !== 0) : SAMPLES
  for (const [name, kind] of Object.entries(types)) {
    if (kind !== 'number') continue
    for (const n of samples) {
      const values = Object.fromEntries(
        Object.entries(types).map(([k, t]) => [
          k,
          t === 'number' ? (k === name ? n : 7) : t === 'select' ? 'other' : t === 'tag' ? (c) => c.join('') : 'X',
        ]),
      )
      const said = String(new IntlMessageFormat(english, 'en').format(values))
      if (!saysNumber(said, n, 'en')) continue
      const got = String(new IntlMessageFormat(translated, locale).format(values))
      if (!saysNumber(got, n, locale)) {
        problems.add(`with ${name} = ${n} it reads "${got}", which does not say ${n}; use # there`)
      }
    }
  }
}

function args(message, locale, problems) {
  const found = new Set()
  walk(new IntlMessageFormat(message, locale).getAst(), found, locale, problems)
  return found
}

const { locale, items } = JSON.parse(readFileSync(0, 'utf8'))
const out = {}
for (const [key, [english, translated]] of Object.entries(items)) {
  const problems = new Set()
  named = new Set()
  try {
    const want = [...args(english, 'en', new Set())].sort()
    const got = [...args(translated, locale, problems)].sort()
    if (want.join() !== got.join()) problems.add(`arguments ${got} differ from ${want}`)
    else countProblems(english, translated, locale, problems)
  } catch (err) {
    problems.add(`does not compile: ${err.message}`)
  }
  if (problems.size) out[key] = [...problems]
}
process.stdout.write(JSON.stringify(out))
