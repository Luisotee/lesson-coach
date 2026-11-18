import { expect, test, type Page, type Route } from '@playwright/test'
import { IntlMessageFormat } from 'intl-messageformat'
import { readFileSync } from 'node:fs'
import { LANGUAGES } from '../src/i18n/languages.ts'
import { checkState, expectNoSideScroll, expectNothingClipped } from './a11y.ts'
import { fixture } from './api.ts'

// Right-to-left pages against the real build and the real translated packs (no mocks). With
// SCREENSHOTS=1 the pages are also saved to docs/screenshots/ for the README and reviewers;
// otherwise the committed screenshots are left alone.

const RTL = LANGUAGES.filter((l) => l.dir === 'rtl').map((l) => l.code)

const PAGES = [
  ['home', '/'],
  ['topic', '/topics/linear-equations'],
  ['practice', '/practice/fractions/1'],
] as const

test('at least two right-to-left languages are listed', () => {
  expect(RTL.length).toBeGreaterThanOrEqual(2)
})

test('the language picker fits a 320 px phone in every language', async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 800 })
  for (const { code } of LANGUAGES) {
    await page.goto(`/?lng=${code}`)
    await expect(page.locator('html')).toHaveAttribute('lang', code)
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
    )
    expect(overflow, code).toBeLessThanOrEqual(0)
  }
})

for (const lang of RTL) {
  for (const [name, path] of PAGES) {
    test(`${lang} ${name} renders right to left with math left to right`, async ({ page }) => {
      await page.setViewportSize({ width: 1280, height: 900 })
      await page.goto(`${path}?lng=${lang}`)
      const html = page.locator('html')
      await expect(html).toHaveAttribute('dir', 'rtl')
      await expect(html).toHaveAttribute('lang', lang)
      await expect(page.getByRole('heading', { level: 1 })).toBeVisible()
      await page.waitForLoadState('networkidle')

      // Math stays left to right inside the right-to-left page: every math expression and
      // equation line, found by what it is (role="math") rather than by its dir attribute.
      const math = page.locator('[role="math"]')
      if (name !== 'home') await expect(math.first()).toBeVisible()
      for (const el of await math.all()) {
        await expect(el).toHaveCSS('direction', 'ltr')
      }
      // Akelius's lesson titles are English: marked so a screen reader reads them in English.
      if (name === 'topic') {
        const titles = page.locator('a[href*="akelius.education"] [lang="en"]')
        await expect(titles.first()).toBeVisible()
        expect(await titles.first().textContent()).toMatch(/[a-z]/i)
      }
      // The text itself runs right to left: the main heading is aligned to the right edge.
      await expect(page.getByRole('heading', { level: 1 })).toHaveCSS('direction', 'rtl')

      // Nothing overflows the page sideways, on a desktop or a phone.
      for (const width of [1280, 360]) {
        await page.setViewportSize({ width, height: 900 })
        const overflow = await page.evaluate(
          () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
        )
        expect(overflow, `${lang} ${name} at ${width}px`).toBeLessThanOrEqual(0)
      }
      if (process.env.SCREENSHOTS === '1') {
        await page.setViewportSize({ width: 1280, height: 900 })
        await page.screenshot({ path: `../docs/screenshots/rtl-${lang}-${name}.png` })
      }
    })
  }
}

/*
 * T11 phase 2: the accessibility checks in other languages, against the real build and the
 * real translated packs. Only the two model calls (mistake, check-working) are mocked, with the
 * same fixtures as the English matrix (e2e/a11y.spec.ts); their prose stays English and is
 * marked lang="en", as a real result in another language would be marked with its own.
 */

/** A locale file's string by dotted key. */
const LOCALES = new Map<string, Record<string, unknown>>()
function t(lang: string, key: string): string {
  if (!LOCALES.has(lang))
    LOCALES.set(
      lang,
      JSON.parse(readFileSync(new URL(`../src/locales/${lang}.json`, import.meta.url), 'utf8')),
    )
  const value = key
    .split('.')
    .reduce<unknown>((o, k) => (o as Record<string, unknown>)?.[k], LOCALES.get(lang))
  if (typeof value !== 'string') throw new Error(`${lang}: no string at ${key}`)
  return value
}

async function mockModel(page: Page) {
  const reply = (path: string) => (route: Route) =>
    route.fulfill({ contentType: 'application/json', body: JSON.stringify(fixture(path)) })
  await page.route('**/api/mistake', reply('mistake/diagnosed.json'))
  await page.route('**/api/check-working', reply('check/bad-line.json'))
}

async function mistakeResult(page: Page, lang: string, fixturePath: string) {
  await page.route('**/api/mistake', (route) =>
    route.fulfill({ contentType: 'application/json', body: JSON.stringify(fixture(fixturePath)) }),
  )
  await page.goto(`/mistake?lng=${lang}`)
  const fields = page.locator('math-field')
  await fields.nth(0).focus()
  await page.keyboard.type('1/2+1/3')
  await fields.nth(1).focus()
  await page.keyboard.type('2/5')
  await page.getByRole('button', { name: t(lang, 'mistake.explain') }).click()
}

/** Every page, in a settled state worth checking, by the active language. */
const LANG_STATES: [string, (page: Page, lang: string) => Promise<void>][] = [
  [
    'home',
    async (page, lang) => {
      await page.goto(`/?lng=${lang}`)
      await expect(
        page.getByRole('link', { name: t(lang, 'topics.fractions.title') }),
      ).toBeVisible()
    },
  ],
  [
    'topic, a step explained with its picture',
    async (page, lang) => {
      await page.goto(`/topics/linear-equations?lng=${lang}`)
      await page.locator('#example [aria-pressed]').nth(1).click()
      const dialog = page.getByRole('dialog')
      // Below 768 px the explanation opens in a bottom sheet.
      const scope = (await dialog.count()) ? dialog : page.locator('#example')
      const tab = scope.getByRole('tab', { name: t(lang, 'topic.modes.visual') })
      await tab.click()
      await expect(tab).toHaveAttribute('aria-selected', 'true')
    },
  ],
  [
    'practice, a line that does not follow and a hint',
    async (page, lang) => {
      await page.goto(`/practice/linear-equations/1?lng=${lang}`)
      await page
        .getByRole('tab', { name: t(lang, 'input.mode.type') })
        .first()
        .click()
      await page.locator('math-field').first().focus()
      await page.keyboard.type('8x=56')
      await page.getByRole('button', { name: t(lang, 'practice.check') }).click()
      await expect(page.locator('[data-check="line_doesnt_follow"]')).toBeVisible()
      await page.getByRole('button', { name: t(lang, 'practice.showNextHint') }).click()
    },
  ],
  [
    'mistake, diagnosed',
    async (page, lang) => {
      await mistakeResult(page, lang, 'mistake/diagnosed.json')
      await expect(page.locator('[data-status="diagnosed"]')).toBeVisible()
    },
  ],
  [
    'mistake, unclear',
    async (page, lang) => {
      await mistakeResult(page, lang, 'mistake/unclear.json')
      await expect(page.locator('[data-status="unclear"]')).toBeVisible()
    },
  ],
  [
    'not found',
    async (page, lang) => {
      await page.goto(`/no-such-page?lng=${lang}`)
      await expect(page.getByRole('heading', { level: 1 })).toBeVisible()
    },
  ],
]

/** Arabic at every layout of the English matrix; a non-Latin LTR script at two; Hindi at one. */
const LAYOUTS: { lang: string; name: string; use: Parameters<typeof test.use>[0] }[] = [
  { lang: 'ar', name: 'desktop', use: { viewport: { width: 1280, height: 800 } } },
  { lang: 'ar', name: '320 px', use: { viewport: { width: 320, height: 800 } } },
  {
    lang: 'ar',
    name: '200% zoom',
    use: { viewport: { width: 640, height: 400 }, deviceScaleFactor: 2 },
  },
  { lang: 'zh-Hans', name: 'desktop', use: { viewport: { width: 1280, height: 800 } } },
  { lang: 'zh-Hans', name: '320 px', use: { viewport: { width: 320, height: 800 } } },
  { lang: 'hi', name: 'desktop', use: { viewport: { width: 1280, height: 800 } } },
]

for (const layout of LAYOUTS) {
  test.describe(`${layout.lang} at ${layout.name}`, () => {
    test.use(layout.use)
    for (const [name, reach] of LANG_STATES) {
      test(`${name}: axe, reflow, nothing clipped`, async ({ page }) => {
        await mockModel(page)
        await reach(page, layout.lang)
        const html = page.locator('html')
        await expect(html).toHaveAttribute('lang', layout.lang)
        await expect(html).toHaveAttribute('dir', layout.lang === 'ar' ? 'rtl' : 'ltr')
        for (const el of await page.locator('[role="math"]').all())
          await expect(el).toHaveCSS('direction', 'ltr')
        await explainSettledIn(page, layout.lang)
        await checkState(page, `${layout.lang} ${name}`)
      })
    }
  })
}

/** "Explain this" fades back from its disabled look; axe must not catch it mid-fade. */
async function explainSettledIn(page: Page, lang: string) {
  const button = page.getByRole('button', { name: t(lang, 'mistake.explain') })
  if (await button.count()) await expect(button).toHaveCSS('opacity', '1')
}

test.describe('print in Arabic', () => {
  test.use({ viewport: { width: 794, height: 1123 } })

  for (const [name, path] of [
    ['topic outline', '/topics/linear-equations'],
    ['practice with a hint', '/practice/linear-equations/1'],
  ] as const) {
    test(`${name}: right to left, math left to right, nothing cut off`, async ({ page }) => {
      await page.goto(`${path}?lng=ar`)
      await expect(page.getByRole('heading', { level: 1 })).toBeVisible()
      if (name.startsWith('practice'))
        await page.getByRole('button', { name: t('ar', 'practice.showNextHint') }).click()
      await page.emulateMedia({ media: 'print' })
      await expect(page.locator('header').first()).toBeHidden()
      await expect(page.locator('html')).toHaveAttribute('dir', 'rtl')
      await expect(page.getByRole('heading', { level: 1 })).toHaveCSS('direction', 'rtl')
      const math = page.locator('[role="math"]').filter({ visible: true })
      await expect(math.first()).toBeVisible()
      for (const el of await math.all()) await expect(el).toHaveCSS('direction', 'ltr')
      if (name.startsWith('topic')) await expect(page.locator('[data-print]')).toBeVisible()
      await expectNoSideScroll(page)
      await expectNothingClipped(page)
    })
  }
})

/*
 * Spoken math in every shipped language: the label of "2x + 6 = 10" in the topic's idea is
 * built from that locale's own math.speech templates, so a screen reader reads it in the page's
 * language. The expected text is formatted here from the locale file with the same ICU syntax.
 */
for (const { code } of LANGUAGES) {
  test(`${code}: math is spoken in the active language`, async ({ page }) => {
    const say = (key: string, values: Record<string, string>) =>
      new IntlMessageFormat(t(code, `math.speech.${key}`), code).format(values) as string
    const expected = say('equals', {
      left: say('plus', { left: say('juxtaposed', { left: '2', right: 'x' }), right: '6' }),
      right: '10',
    })
    await page.goto(`/topics/linear-equations?lng=${code}`)
    await expect(page.locator('html')).toHaveAttribute('lang', code)
    const math = page.locator('#idea [role="math"]').filter({ hasText: /=/ }).first()
    await expect(math).toHaveAttribute('aria-label', expected)
    await expect(math).toHaveCSS('direction', 'ltr')
    if (code !== 'en') expect(expected, 'not the English reading').not.toBe('2 x plus 6 equals 10')
  })
}

/*
 * Fonts: each shipped script draws with the web font meant for it, never a system fallback (a
 * missing glyph would be drawn by a system font or as tofu). Chromium reports the fonts it
 * actually used for a node's text over CDP.
 */
const SCRIPT_FONTS: Record<string, { lang: string; sans: RegExp; hand: RegExp }> = {
  latin: { lang: 'en', sans: /^Inter/, hand: /^Kalam/ },
  cyrillic: { lang: 'ru', sans: /^Inter/, hand: /^Playpen Sans/ },
  greek: { lang: 'el', sans: /^Inter/, hand: /^Playpen Sans/ },
  arabic: { lang: 'ar', sans: /^Noto Sans Arabic/, hand: /^Noto Sans Arabic/ },
  devanagari: { lang: 'hi', sans: /^Noto Sans Devanagari/, hand: /^Kalam/ },
  bengali: { lang: 'bn', sans: /^Noto Sans Bengali/, hand: /^Noto Sans Bengali/ },
  hans: { lang: 'zh-Hans', sans: /^Noto Sans SC/, hand: /^Noto Sans SC/ },
}

test('every shipped language has a script with a font check', () => {
  const scripts = new Set(LANGUAGES.map((l) => l.script))
  expect([...scripts].sort()).toEqual(Object.keys(SCRIPT_FONTS).sort())
})

for (const [script, { lang, sans, hand }] of Object.entries(SCRIPT_FONTS)) {
  test(`${script} (${lang}) renders in its own web fonts`, async ({ page, browserName }) => {
    test.skip(browserName !== 'chromium', 'CDP is Chromium only')
    await page.goto(`/topics/linear-equations?lng=${lang}`)
    await expect(page.locator('#idea')).toBeVisible()
    await page.evaluate(() => document.fonts.ready)
    const cdp = await page.context().newCDPSession(page)
    await cdp.send('DOM.enable')
    await cdp.send('CSS.enable')
    const { root } = await cdp.send('DOM.getDocument', { depth: -1 })
    const fontsOf = async (selector: string) => {
      const { nodeId } = await cdp.send('DOM.querySelector', { nodeId: root.nodeId, selector })
      expect(nodeId, `${lang} ${selector}`).toBeTruthy()
      return (await cdp.send('CSS.getPlatformFontsForNode', { nodeId })).fonts
    }
    for (const [selector, family] of [
      ['main p', sans],
      ['header nav a', sans],
      ['main p.font-hand', hand],
    ] as const) {
      // Fonts load when the language becomes active; wait until the text is drawn with them.
      await expect
        .poll(async () => (await fontsOf(selector)).map((f) => f.familyName).join(', '), {
          message: `${lang} ${selector}`,
        })
        .toMatch(new RegExp(`(^|, )${family.source.slice(1)}`))
      const fonts = await fontsOf(selector)
      const system = fonts.filter((f) => !f.isCustomFont).map((f) => f.familyName)
      expect(system, `${lang} ${selector}: drawn with system fonts`).toEqual([])
    }
  })
}

/*
 * The language switch on a topic page, by keyboard: lang and dir on <html> follow, focus stays
 * on the picker, and the page's spoken math changes language with it.
 */
test('switching language changes lang, dir and the spoken math, and keeps focus', async ({
  page,
}) => {
  await page.goto('/topics/linear-equations')
  const math = page.locator('#idea [role="math"]').filter({ hasText: /=/ }).first()
  await expect(math).toHaveAttribute('aria-label', '2 x plus 6 equals 10')
  const picker = page.locator('header select')
  await picker.focus()
  const html = page.locator('html')
  // A closed select changes its value on the arrow keys: Arabic is next after English, and
  // End jumps to the last language, Simplified Chinese.
  expect([LANGUAGES[1].code, LANGUAGES.at(-1)?.code]).toEqual(['ar', 'zh-Hans'])
  for (const [key, lang, dir] of [
    ['ArrowDown', 'ar', 'rtl'],
    ['End', 'zh-Hans', 'ltr'],
  ] as const) {
    await page.keyboard.press(key)
    await expect(html).toHaveAttribute('lang', lang)
    await expect(html).toHaveAttribute('dir', dir)
    await expect(picker).toBeFocused()
    await expect(page.getByRole('heading', { level: 1 })).toHaveText(
      t(lang, 'topics.linear-equations.title'),
    )
    // The word for "equals", from translated text: matched as plain text, never as a pattern.
    const equals = t(lang, 'math.speech.equals')
      .replace(/\{\w+\}/g, '')
      .trim()
    await expect.poll(() => math.getAttribute('aria-label')).toContain(equals)
    await expect(math).toHaveCSS('direction', 'ltr')
  }
})
