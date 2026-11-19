import { expect, test } from '@playwright/test'
import {
  chooseLanguage,
  expectNoAxeViolations,
  languageButton,
  openLanguageMenu,
  t,
} from './a11y.ts'
import { LANGUAGES } from '../src/i18n/languages.ts'
import { mockApi } from './api.ts'

test.beforeEach(async ({ page }) => {
  await mockApi(page)
})

const ROUTES = [
  ['/', 'Feel sure of the math before you teach it.'],
  ['/topics/linear-equations', 'Solving linear equations'],
  ['/mistake', 'A student wrote this…'],
  ['/practice/fractions/2', 'Practice: Fractions'],
  ['/no-such-page', 'Page not found'],
] as const

test('the API is up', async ({ request }) => {
  const res = await request.get('/api/health')
  expect(res.ok()).toBe(true)
})

for (const [path, heading] of ROUTES) {
  test(`${path} renders and has no axe violations`, async ({ page }) => {
    await page.goto(path)
    await expect(page.getByRole('heading', { level: 1 })).toHaveText(heading)
    await expectNoAxeViolations(page)
  })
}

test('the skip link is the first tab stop and moves focus to main', async ({ page }) => {
  await page.goto('/')
  await page.keyboard.press('Tab')
  const skip = page.getByRole('link', { name: 'Skip to main content' })
  await expect(skip).toBeFocused()
  await expect(skip).toBeVisible()
  await page.keyboard.press('Enter')
  await expect(page.locator('main')).toBeFocused()
})

test('every header and home link reaches a real page', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByRole('link', { name: /Solving linear equations/ })).toBeVisible()
  const hrefs = await page
    .locator('header a, main a')
    .evaluateAll((links) => [...new Set(links.map((a) => a.getAttribute('href') ?? ''))])
  expect(hrefs.length).toBeGreaterThan(6)
  for (const href of hrefs) {
    await page.goto(href)
    await expect(page.locator('[data-state="loading"]')).toHaveCount(0)
    await expect(page.getByRole('heading', { level: 1 }), href).not.toHaveText('Page not found')
  }
})

test('the Topics link moves to the topic list', async ({ page }) => {
  await page.goto('/mistake')
  await page.getByRole('link', { name: 'Topics', exact: true }).click()
  await expect(page).toHaveURL(/\/#topics$/)
  await expect(page.locator('#topics')).toBeFocused()
  await expect(page.locator('#topics')).toBeInViewport()
})

test('Back returns to where the page was scrolled', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 500 })
  await page.goto('/')
  const link = page.getByRole('link', { name: /Fractions/ })
  await link.waitFor()
  await page.evaluate(() => window.scrollTo(0, 400))
  await expect.poll(() => page.evaluate(() => window.scrollY)).toBe(400)
  // Clicking may scroll the link into view first; Back must return to where we were then.
  await link.scrollIntoViewIfNeeded()
  const before = await page.evaluate(() => window.scrollY)
  expect(before).toBeGreaterThan(100)
  await link.click()
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Fractions')
  await expect(page.getByRole('heading', { level: 1 })).toBeFocused()
  await page.goBack()
  await expect(page.getByRole('heading', { level: 1 })).toHaveText(
    'Feel sure of the math before you teach it.',
  )
  // Within a few pixels: late layout (fonts) can shift the restored position slightly.
  // The bug this guards against restores to 0.
  await expect
    .poll(async () => Math.abs((await page.evaluate(() => window.scrollY)) - before))
    .toBeLessThanOrEqual(10)
})

test('the language picker switches to Arabic, right to left, and remembers it', async ({
  page,
}) => {
  await page.goto('/')
  await expect(page.locator('html')).toHaveAttribute('dir', 'ltr')
  await chooseLanguage(page, 'العربية')
  await expect(page.locator('html')).toHaveAttribute('lang', 'ar')
  await expect(page.locator('html')).toHaveAttribute('dir', 'rtl')
  await expect(page.getByRole('link', { name: t('ar', 'nav.topics') })).toBeVisible()

  await page
    .getByRole('link', { name: t('ar', 'nav.mistake') })
    .first()
    .click()
  await expect(page.getByRole('heading', { level: 1 })).toHaveText(t('ar', 'mistake.title'))
  await page.reload()
  await expect(page.locator('html')).toHaveAttribute('dir', 'rtl')
  await expect(page.getByRole('heading', { level: 1 })).toHaveText(t('ar', 'mistake.title'))
})

test('the language menu: native names, one machine-translation note, and the privacy line', async ({
  page,
}) => {
  await page.setViewportSize({ width: 1280, height: 800 })
  await page.goto('/')
  // Logo, nav and the language button fit on one row.
  expect((await page.locator('header').boundingBox())?.height).toBeLessThanOrEqual(80)
  await expect(languageButton(page)).toHaveAccessibleName('Language: English')
  const menu = await openLanguageMenu(page)
  const items = menu.getByRole('menuitemradio')
  await expect(items).toHaveCount(LANGUAGES.length)
  await expect(items).toHaveText(LANGUAGES.map((l) => l.nativeName))
  await expect(menu.getByRole('menuitemradio', { name: 'English' })).toBeChecked()
  // One note, read as the menu's description, instead of a suffix on every row.
  await expect(menu).toHaveAccessibleDescription(t('en', 'language.note'))
  await expect(menu).toContainText(t('en', 'shell.nothingSaved'))
  await expect(menu).not.toContainText('machine-translated)')
  await expectNoAxeViolations(page)
  await page.keyboard.press('Escape')
  // English is the original: the footer adds no machine-translation note.
  await expect(page.locator('footer')).not.toContainText(t('ar', 'shell.machineNote'))
  await expect(page.locator('footer')).toContainText(t('en', 'shell.nothingSaved'))

  await chooseLanguage(page, 'العربية')
  await expect(languageButton(page)).toHaveAccessibleName(
    t('ar', 'language.button').replace('{name}', 'العربية'),
  )
  await expect(page.locator('footer')).toContainText(t('ar', 'shell.machineNote'))
  const rtlMenu = await openLanguageMenu(page)
  await expect(rtlMenu).toHaveAttribute('dir', 'rtl')
  await expect(rtlMenu.getByRole('menuitemradio', { name: 'العربية' })).toBeChecked()
  await expectNoAxeViolations(page)
})

test('the dev showcases are not in the production build', async ({ page }) => {
  for (const path of ['/demo/math', '/demo/input']) {
    await page.goto(path)
    await expect(page.getByRole('heading', { level: 1 }), path).toHaveText('Page not found')
  }
})

test('Practice opens the first problem of the first topic that has practice', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('link', { name: 'Practice', exact: true }).click()
  await expect(page).toHaveURL(/\/practice\/negative-numbers\/1$/)
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Practice: Negative numbers')
  await page.goBack()
  await expect(page).toHaveURL(/\/$/)
})

test('pages reflow at 320 px without horizontal scrolling', async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 800 })
  for (const [path] of ROUTES) {
    await page.goto(path)
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
    )
    expect(overflow, path).toBeLessThanOrEqual(0)
  }
})
