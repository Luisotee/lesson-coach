import { expect, test } from '@playwright/test'
import { LANGUAGES } from '../src/i18n/languages.ts'

// Right-to-left pages against the real build and the real translated packs (no mocks). The
// screenshots go to docs/screenshots/ so a reviewer can see the pages without running them.

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

      // Math stays left to right inside the right-to-left page.
      const math = page.locator('[dir="ltr"]')
      if (name !== 'home') await expect(math.first()).toBeVisible()
      for (const el of await math.all()) {
        await expect(el).toHaveCSS('direction', 'ltr')
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
      await page.setViewportSize({ width: 1280, height: 900 })
      await page.screenshot({
        path: `../docs/screenshots/rtl-${lang}-${name}.png`,
        fullPage: false,
      })
    })
  }
}
