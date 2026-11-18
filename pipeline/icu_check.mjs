// Checks translated ICU messages against their English: the message compiles for its locale
// with intl-messageformat (what i18next-icu uses), has the same arguments, and every plural
// uses only the locale's CLDR categories (plus any `=N`), always with `other`, and all of them
// where the English names a category such as `one`.
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
        const missing = named.has(el.value) ? wanted.filter((k) => !categories.includes(k)) : []
        if (extra.length) problems.add(`{${el.value}, plural}: ${extra} not used in ${locale}`)
        if (missing.length) problems.add(`{${el.value}, plural} needs ${missing} for ${locale}`)
      }
      for (const option of Object.values(el.options)) walk(option.value, found, locale, problems)
    }
    if (el.type === TAG) walk(el.children, found, locale, problems)
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
  } catch (err) {
    problems.add(`does not compile: ${err.message}`)
  }
  if (problems.size) out[key] = [...problems]
}
process.stdout.write(JSON.stringify(out))
