import AxeBuilder from '@axe-core/playwright'
import { expect, test, type Page } from '@playwright/test'
import { mockApi } from './api.ts'

const AXE_TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa']

async function expectNoAxeViolations(page: Page) {
  const results = await new AxeBuilder({ page }).withTags(AXE_TAGS).analyze()
  expect(results.violations).toEqual([])
}

test.beforeEach(async ({ page }) => {
  await mockApi(page)
})

const ROUTES = [
  ['/', 'Feel sure of the math before you teach it.'],
  ['/topics/linear-equations', 'Solving linear equations'],
  ['/mistake', 'A student wrote this'],
  ['/practice/fractions/2', 'Practice: Fractions'],
  ['/demo/math', 'Math handwriting components'],
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
  const hrefs = await page
    .locator('header a, main a')
    .evaluateAll((links) => [...new Set(links.map((a) => a.getAttribute('href') ?? ''))])
  expect(hrefs.length).toBeGreaterThan(6)
  for (const href of hrefs) {
    await page.goto(href)
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
  await page.getByLabel('Language').selectOption('ar')
  await expect(page.locator('html')).toHaveAttribute('lang', 'ar')
  await expect(page.locator('html')).toHaveAttribute('dir', 'rtl')
  await expect(page.getByRole('link', { name: 'المواضيع' })).toBeVisible()

  await page.getByRole('link', { name: 'كتب طالب هذا' }).first().click()
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('كتب طالب هذا')
  await page.reload()
  await expect(page.locator('html')).toHaveAttribute('dir', 'rtl')
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('كتب طالب هذا')
})

test.describe('math demo', () => {
  for (const lng of ['en', 'ar']) {
    test(`renders in ${lng} with math left to right and no axe violations`, async ({ page }) => {
      await page.goto(`/demo/math?lng=${lng}`)
      await expect(page.locator('html')).toHaveAttribute('dir', lng === 'ar' ? 'rtl' : 'ltr')
      await expect(page.getByTestId('rtl-panel')).toHaveAttribute('dir', 'rtl')
      // Every expression and notebook line is LTR, even inside RTL text.
      const dirs = await page
        .locator('[role="math"]')
        .evaluateAll((els) => els.map((el) => getComputedStyle(el).direction))
      expect(dirs.length).toBeGreaterThan(10)
      expect(new Set(dirs)).toEqual(new Set(['ltr']))
      expect(await page.locator('ol[aria-label]').count()).toBeGreaterThanOrEqual(4)
      await expectNoAxeViolations(page)
    })
  }

  test('lines align on = across a notebook', async ({ page }) => {
    await page.goto('/demo/math')
    const notebook = page.getByRole('list', { name: 'Solving 3x + 5 = 20' }).first()
    const eqXs = await notebook
      .locator('[data-math="line"] > span:nth-child(2)')
      .evaluateAll((cells) => cells.map((c) => Math.round(c.getBoundingClientRect().left)))
    expect(eqXs).toHaveLength(3)
    expect(new Set(eqXs).size).toBe(1)
  })

  test('the write-on animation is off under reduced motion', async ({ page }) => {
    await page.goto('/demo/math')
    await expect(page.getByRole('button', { name: 'Write it again' })).toHaveCount(0)
    const line = page.locator('[data-math="line"]').first()
    expect(await line.evaluate((el) => getComputedStyle(el).animationName)).toBe('none')
  })

  test.describe('without reduced motion', () => {
    test.use({ reducedMotion: 'no-preference' })
    test('lines are written on', async ({ page }) => {
      await page.goto('/demo/math')
      const line = page.locator('[data-math="line"]').first()
      expect(await line.evaluate((el) => getComputedStyle(el).animationName)).toBe('write')
      await expect(page.getByRole('button', { name: 'Write it again' })).toBeVisible()
    })
  })
})

test('at 320 px a long notebook line scrolls inside the notebook, focusable and labelled', async ({
  page,
}) => {
  await page.setViewportSize({ width: 320, height: 800 })
  await page.goto('/demo/math')
  const region = page.getByRole('region', { name: 'Solving 2(x + 3) − 4(x − 1) = 3x + 10' })
  await expect(region).toHaveAttribute('tabindex', '0')
  expect(await region.evaluate((el) => el.scrollWidth > el.clientWidth)).toBe(true)
  await expectNoAxeViolations(page)
})

test('at 1280 px the same notebook fits and is not a tab stop', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 800 })
  await page.goto('/demo/math')
  const list = page.getByRole('list', { name: 'Solving 2(x + 3) − 4(x − 1) = 3x + 10' })
  await expect(list).toBeVisible()
  await expect(list.locator('xpath=..')).not.toHaveAttribute('tabindex')
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
