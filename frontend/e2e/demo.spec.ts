import AxeBuilder from '@axe-core/playwright'
import { expect, test, type Page } from '@playwright/test'

// The math components showcase, which only the dev server has (see playwright.config.ts).

const AXE_TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa']

async function expectNoAxeViolations(page: Page) {
  const results = await new AxeBuilder({ page }).withTags(AXE_TAGS).analyze()
  expect(results.violations).toEqual([])
}

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
    // evaluateAll doesn't wait: let the lazily loaded page render its lines first.
    const cells = notebook.locator('[data-math="line"] > span:nth-child(2)')
    await expect(cells).toHaveCount(3)
    const eqXs = await cells.evaluateAll((cells) =>
      cells.map((c) => Math.round(c.getBoundingClientRect().left)),
    )
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
