import AxeBuilder from '@axe-core/playwright'
import { expect, type Page } from '@playwright/test'
import { readFileSync } from 'node:fs'

/** WCAG 2.0, 2.1 and 2.2 A and AA. `wcag22aa` brings axe's `target-size` (2.5.8). */
export const AXE_TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa']

export async function expectNoAxeViolations(page: Page, label?: string) {
  const results = await new AxeBuilder({ page }).withTags(AXE_TAGS).analyze()
  // Only what a reader needs to find the problem: the rule and the elements.
  const found = results.violations.map((v) => ({
    rule: v.id,
    targets: v.nodes.map((n) => `${n.target.join(' ')}: ${n.failureSummary ?? ''}`),
  }))
  expect(found, label).toEqual([])
}

/** WCAG 1.4.10 reflow: the page itself never scrolls sideways. */
export async function expectNoSideScroll(page: Page, label?: string) {
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
  )
  expect(overflow, label).toBeLessThanOrEqual(0)
}

/**
 * Nothing is cut off: no visible element that hides its overflow is holding more than it
 * shows. Screen-reader-only text (a 1 px box by design) and the hidden parts of closed
 * widgets are skipped. Scroll regions (`overflow: auto`) are not clipping: they scroll, and
 * axe checks that they can be reached by keyboard.
 */
export async function expectNothingClipped(page: Page, label?: string) {
  const clipped = await page.evaluate(() => {
    const out: string[] = []
    for (const el of document.querySelectorAll<HTMLElement>('body *')) {
      const style = getComputedStyle(el)
      const hides = (v: string) => v === 'hidden' || v === 'clip'
      if (!hides(style.overflowX) && !hides(style.overflowY)) continue
      if (style.visibility === 'hidden' || el.closest('[aria-hidden="true"], [hidden], [inert]'))
        continue
      // MathLive's on-screen keyboard and its popovers (touch devices) are its own layout,
      // with off-screen layers by design; axe still checks them.
      if (el.closest('.ML__keyboard, [id^="ML__"]')) continue
      const box = el.getBoundingClientRect()
      if (box.width <= 1 || box.height <= 1) continue // collapsed accordion panels
      if (style.clipPath === 'inset(50%)' || style.clip === 'rect(0px, 0px, 0px, 0px)') continue // sr-only
      if (!el.innerText?.trim()) continue // decoration: bars, rings, images
      const wide = hides(style.overflowX) && el.scrollWidth > el.clientWidth + 1
      const tall = hides(style.overflowY) && el.scrollHeight > el.clientHeight + 1
      if (wide || tall) {
        const name = el.tagName.toLowerCase() + (el.id ? `#${el.id}` : '')
        out.push(`${name} "${el.innerText.trim().slice(0, 40)}" ${wide ? 'wide' : 'tall'}`)
      }
    }
    return out
  })
  expect(clipped, label).toEqual([])
}

/** Every check a page state must pass, at whatever layout the project gives it. */
export async function checkState(page: Page, label?: string, { loading = false } = {}) {
  // A state is checked once it has settled, unless the loading state is what's checked.
  if (!loading) await expect(page.locator('[data-state="loading"]').first()).toBeHidden()
  await expectNoSideScroll(page, label)
  await expectNothingClipped(page, label)
  await expectNoAxeViolations(page, label)
}

/**
 * Waits until "Explain this" (by its name in the active language) is back from its disabled
 * look (opacity 0.5). The fade is 0.01 ms under reduced motion, but a busy machine can still be
 * caught in it by axe's contrast check.
 */
export async function explainSettled(page: Page, name = 'Explain this') {
  await expect(page.getByRole('button', { name })).toHaveCSS('opacity', '1')
}

const LOCALES = new Map<string, Record<string, unknown>>()

/**
 * A string from a locale file by dotted key, raw (ICU placeholders left in). Read from the
 * file, not hard-coded, because the translation pipeline may rewrite it.
 */
export function t(lang: string, key: string): string {
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

/** Types into a MathLive field by its label. */
export async function typeMath(page: Page, label: string, keys: string) {
  const field = page.locator(`math-field[aria-label="${label}"]`)
  await field.focus()
  await page.keyboard.type(keys)
}
