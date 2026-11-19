import { expect, test, type Locator, type Page } from '@playwright/test'
import { expectNoAxeViolations, explainSettled, languageButton } from './a11y.ts'
import { fixture, mockApi } from './api.ts'

/*
 * Each page's main task done with the keyboard alone: no clicks, no programmatic focus.
 * Every element focus lands on along the way must show a focus indicator (WCAG 2.4.7) with
 * enough contrast (1.4.11), and must not be hidden under the sticky header (WCAG 2.4.11).
 */

/**
 * What is wrong with the focused element, or null. Runs in the page.
 *
 * The indicator must be an outline or a ring (a box-shadow with no blur) at least 2 px wide,
 * in a colour with 3:1 contrast against white and against the element's own fill, unless an
 * offset separates them (WCAG 1.4.11), and it must go away when focus moves on: the element
 * focused before this one is checked again, unfocused.
 */
async function focusProblem(): Promise<string | null> {
  // Let the focus style's transition finish (0.01 ms under reduced motion, but only on the
  // next frame), so the ring is read as it shows. Only running, finite animations are waited
  // for, and never more than 500 ms: a paused one would otherwise hang the test.
  const settled = Promise.all(
    document
      .getAnimations()
      .filter((a) => a.playState === 'running' && a.effect?.getTiming().iterations !== Infinity)
      .map((a) => a.finished.catch(() => {})),
  )
  await Promise.race([settled, new Promise((r) => setTimeout(r, 500))])
  await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)))
  const el = document.activeElement as HTMLElement | null
  if (!el || el === document.body) return 'nothing focused'
  const label = (e: Element) =>
    `${e.tagName.toLowerCase()} "${(e.getAttribute('aria-label') ?? e.textContent ?? '').trim().slice(0, 40)}"`
  const name = label(el)

  // Any CSS colour (rgb, oklab, color-mix…) is read back as 8-bit RGBA by painting it on a
  // 1×1 canvas, so the contrast maths never guesses at a colour space.
  const ctx = document.createElement('canvas').getContext('2d', { willReadFrequently: true })!
  const rgba = (color: string): [number, number, number, number] => {
    ctx.clearRect(0, 0, 1, 1)
    ctx.fillStyle = '#000'
    ctx.fillStyle = color
    ctx.fillRect(0, 0, 1, 1)
    const [r, g, b, a] = ctx.getImageData(0, 0, 1, 1).data
    return [r, g, b, a / 255]
  }
  /** A colour's relative luminance, alpha-blended over white. */
  const luminance = (color: string) => {
    const [r, g, b, a] = rgba(color)
    const lum = [r, g, b]
      .map((c) => (a * c + (1 - a) * 255) / 255)
      .map((c) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4))
    return 0.2126 * lum[0] + 0.7152 * lum[1] + 0.0722 * lum[2]
  }
  const contrast = (a: string, b = 'rgb(255, 255, 255)') => {
    const [x, y] = [luminance(a), luminance(b)].sort((m, n) => n - m)
    return (x + 0.05) / (y + 0.05)
  }
  const alpha = (color: string) => rgba(color)[3]
  /** The colour function in a computed value, whatever its colour space. */
  const COLOR = /(?:rgba?|hsla?|hwb|lab|lch|oklab|oklch|color)\([^)]*\)/
  /**
   * The element's focus indicator as text, or '' if it shows none that is strong enough. It
   * must contrast 3:1 with the page around it (white) and with what it touches inside: the
   * element's own background, unless an offset or a gap ring sits in between.
   */
  const indicator = (e: Element) => {
    const s = getComputedStyle(e)
    const fill = alpha(s.backgroundColor) > 0 ? s.backgroundColor : 'rgb(255, 255, 255)'
    const strong: string[] = []
    const inside = parseFloat(s.outlineOffset) > 0 ? 'rgb(255, 255, 255)' : fill
    if (
      s.outlineStyle !== 'none' &&
      parseFloat(s.outlineWidth) >= 2 &&
      contrast(s.outlineColor) >= 3 &&
      contrast(s.outlineColor, inside) >= 3
    )
      strong.push(`outline ${s.outlineWidth} ${s.outlineColor}`)
    // Computed box-shadows read "rgb(…) Xpx Ypx BLURpx SPREADpx", comma separated. A ring is
    // one with no offset or blur; a ring offset (Tailwind's ring-offset) is a smaller ring
    // under it, in the gap colour.
    const rings = s.boxShadow
      .split(/,(?![^(]*\))/)
      .flatMap((shadow) => {
        const color = shadow.match(COLOR)?.[0]
        const [x, y, blur, spread] = (shadow.replace(COLOR, '').match(/-?[\d.]+px/g) ?? []).map(
          parseFloat,
        )
        const solid = color && alpha(color) > 0 && !shadow.includes('inset')
        return solid && x === 0 && y === 0 && blur === 0 && spread > 0 ? [{ color, spread }] : []
      })
      .sort((a, b) => b.spread - a.spread)
    if (rings.length) {
      const [outer, gap] = rings
      const width = outer.spread - (gap?.spread ?? 0)
      const touches = gap?.color ?? fill
      if (width >= 2 && contrast(outer.color) >= 3 && contrast(outer.color, touches) >= 3)
        strong.push(`ring ${width}px ${outer.color}`)
    }
    return strong.join(', ')
  }
  // A math field shows its focus on the box around it (a focus-within ring).
  const ringOf = (e: HTMLElement) =>
    e.tagName === 'MATH-FIELD' ? e.closest<HTMLElement>('[class*="focus-within:ring"]') : e
  const ring = ringOf(el)
  const shown = ring ? indicator(ring) : ''
  if (!shown)
    return `${name}: no focus indicator of 2 px or more at 3:1 against the page and its own fill`

  // The previous stop, now unfocused, must have lost its indicator.
  const w = window as unknown as { lastFocus?: { el: HTMLElement; shown: string } }
  const last = w.lastFocus
  w.lastFocus = { el, shown }
  if (last && last.el !== el && last.el.isConnected && !last.el.contains(el)) {
    const lastRing = ringOf(last.el)
    if (lastRing && !lastRing.contains(el) && indicator(lastRing) === last.shown)
      return `${label(last.el)}: still shows its focus indicator (${last.shown}) after focus left`
  }

  const header = document.querySelector('header')
  // A fixed element (the skip link, a sheet) sits above the header, so can't be under it.
  const fixed = (e: Element | null): boolean =>
    !!e && (getComputedStyle(e).position === 'fixed' || fixed(e.parentElement))
  if (
    header &&
    !header.contains(el) &&
    !fixed(el) &&
    getComputedStyle(header).position === 'sticky'
  ) {
    const box = el.getBoundingClientRect()
    const bottom = header.getBoundingClientRect().bottom
    if (box.bottom <= bottom + 1) return `${name}: hidden under the sticky header`
  }
  return null
}

/**
 * Presses Tab (or Shift+Tab) until `target` has focus, checking every stop on the way.
 * Fails if it isn't reached within `max` presses.
 */
async function tabTo(page: Page, target: Locator, { back = false, max = 80 } = {}) {
  for (let i = 0; i < max; i++) {
    await page.keyboard.press(back ? 'Shift+Tab' : 'Tab')
    expect(await page.evaluate(focusProblem), `on the way to ${target}`).toBeNull()
    if (
      await target.evaluate(
        (el) => el === document.activeElement || el.contains(document.activeElement),
      )
    )
      return
  }
  throw new Error(`Tab never reached ${target}`)
}

test.beforeEach(async ({ page }) => {
  await mockApi(page, {
    checkWorking: () => ({ body: fixture('check/bad-line.json') }),
  })
})

test('home to a worked example, its explanations, a question and the outline', async ({ page }) => {
  await page.goto('/')
  await tabTo(page, page.getByRole('link', { name: /Solving linear equations/ }).last())
  await page.keyboard.press('Enter')
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Solving linear equations')
  // The loading view already shows that h1 (and focus lands on it); wait for the pack.
  await expect(page.locator('[data-state="loading"]')).toHaveCount(0)

  const line = page.getByRole('button', { name: /3 x equals 15/ })
  await tabTo(page, line)
  await page.keyboard.press('Enter')
  // Below 768 px (a phone, or 200% zoom) the explanation opens in a sheet; Esc closes it.
  const phone = (page.viewportSize()?.width ?? 1280) < 768
  const scope = phone ? page.getByRole('dialog') : page.locator('#example')
  await tabTo(page, scope.getByRole('tab', { name: 'Why?' }))
  await page.keyboard.press('ArrowRight')
  await expect(scope.getByRole('tab', { name: 'Another way' })).toHaveAttribute(
    'aria-selected',
    'true',
  )
  await page.keyboard.press('ArrowRight')
  await expect(scope.locator('[data-picture="balance"]')).toBeVisible()
  if (phone) await page.keyboard.press('Escape')
  await expect(line).toHaveAttribute('aria-pressed', 'true')

  // Back up to the example's own Next button, then on to the questions.
  await tabTo(page, page.getByRole('button', { name: 'Next worked example' }), { back: true })
  await page.keyboard.press('Enter')
  await expect(page.getByText('worked example 2 of 3')).toBeVisible()
  const question = page.getByRole('button', { name: /Can I just move the 5/ })
  await tabTo(page, question)
  await page.keyboard.press('Enter')
  await expect(question).toHaveAttribute('aria-expanded', 'true')
  await tabTo(page, page.getByRole('link', { name: /Try these problems yourself first/ }))
  await page.keyboard.press('Enter')
  await expect(page).toHaveURL(/\/practice\/linear-equations\/1$/)
})

test('practice: type working, check it, open every hint, start over, next problem', async ({
  page,
}) => {
  await page.goto('/practice/linear-equations/1')
  // The mode tabs: the selected one (Write) is the tab stop; arrows move to Type.
  await tabTo(page, page.getByRole('tab', { name: 'Write' }).first())
  await page.keyboard.press('ArrowLeft')
  await expect(page.getByRole('tab', { name: 'Type' }).first()).toHaveAttribute(
    'aria-selected',
    'true',
  )
  await tabTo(page, page.locator('math-field[aria-label="Your working, line 1"]'))
  await page.keyboard.type('8x=56')
  await tabTo(page, page.getByRole('button', { name: 'Check my working' }))
  await page.keyboard.press('Enter')
  await expect(page.locator('[data-check="line_doesnt_follow"]')).toBeVisible()

  for (let i = 0; i < 4; i++) {
    await tabTo(page, page.getByRole('button', { name: /Show next hint|Show the answer/ }))
    await page.keyboard.press('Enter')
  }
  await expect(page.getByRole('link', { name: 'Open the worked example.' })).toBeVisible()
  await tabTo(page, page.getByRole('button', { name: 'Start over' }), { back: true })
  await page.keyboard.press('Enter')
  await expect(page.getByRole('button', { name: 'Show next hint' })).toBeFocused()
  // Next problem sits under the problem, before the hints panel beside it.
  await tabTo(page, page.getByRole('link', { name: 'Next problem' }), { back: true })
  await page.keyboard.press('Enter')
  await expect(page).toHaveURL(/\/practice\/linear-equations\/2$/)
})

test('mistake: choose a topic, type the problem and answer, explain, try another', async ({
  page,
}) => {
  await page.goto('/mistake')
  await tabTo(page, page.getByRole('button', { name: 'Fractions' }))
  await page.keyboard.press('Space')
  await expect(page.getByRole('button', { name: 'Fractions' })).toHaveAttribute(
    'aria-pressed',
    'true',
  )
  await tabTo(page, page.locator('math-field[aria-label="The problem"]'))
  await page.keyboard.type('1/2+1/3')
  await tabTo(page, page.locator('math-field[aria-label="What your student answered"]'))
  await page.keyboard.type('2/5')
  await tabTo(page, page.getByRole('button', { name: 'Explain this' }))
  await page.keyboard.press('Enter')
  await expect(page.locator('[data-status="diagnosed"]')).toBeVisible()
  await tabTo(page, page.getByRole('button', { name: 'Try another answer' }))
  await page.keyboard.press('Enter')
  await expect(page.locator('math-field[aria-label="What your student answered"]')).toBeFocused()
  await explainSettled(page)
  await expectNoAxeViolations(page)
})

test('the language menu by keyboard: to Arabic and back', async ({ page }) => {
  await page.goto('/')
  const button = languageButton(page)
  await tabTo(page, button)
  const html = page.locator('html')
  // Enter opens the menu on its first row, English; Arabic is next. Choosing closes the menu
  // and gives focus back to the button.
  await page.keyboard.press('Enter')
  await expect(page.getByRole('menuitemradio', { name: 'English' })).toBeFocused()
  await page.keyboard.press('ArrowDown')
  await expect(page.getByRole('menuitemradio', { name: 'العربية' })).toBeFocused()
  await page.keyboard.press('Enter')
  await expect(html).toHaveAttribute('lang', 'ar')
  await expect(html).toHaveAttribute('dir', 'rtl')
  await expect(page.getByRole('menu')).toBeHidden()
  await expect(button).toBeFocused()
  // Escape closes without choosing. Typing jumps to the language whose name starts so (Radix
  // moves focus on the next tick, so each key waits for it); Home goes back to English.
  await page.keyboard.press('Enter')
  await expect(page.getByRole('menu')).toHaveAttribute('dir', 'rtl')
  await page.keyboard.press('Escape')
  await expect(page.getByRole('menu')).toBeHidden()
  await expect(button).toBeFocused()
  await expect(html).toHaveAttribute('lang', 'ar')
  await page.keyboard.press('Space')
  await expect(page.getByRole('menuitemradio', { name: 'English' })).toBeFocused()
  await page.keyboard.type('S')
  await expect(page.getByRole('menuitemradio', { name: 'Svenska' })).toBeFocused()
  await page.keyboard.press('Home')
  await expect(page.getByRole('menuitemradio', { name: 'English' })).toBeFocused()
  await page.keyboard.press('Enter')
  await expect(html).toHaveAttribute('lang', 'en')
  await expect(html).toHaveAttribute('dir', 'ltr')
  await expect(button).toBeFocused()
})

test.describe('on a phone', () => {
  test.use({ viewport: { width: 390, height: 844 } })
  // Its own viewport replaces the zoomed one (2x density), so it would only run twice.
  test.skip(({ deviceScaleFactor }) => deviceScaleFactor === 2)

  test('a step opens in the bottom sheet, moves on, and Esc returns to the line', async ({
    page,
  }) => {
    await page.goto('/topics/linear-equations')
    await tabTo(page, page.getByRole('button', { name: /3 x equals 15/ }))
    await page.keyboard.press('Enter')
    const sheet = page.getByRole('dialog')
    await expect(sheet).toBeVisible()
    await tabTo(page, sheet.getByRole('button', { name: 'Next step' }))
    await page.keyboard.press('Enter')
    await expect(sheet.getByText('Step 3 · divide both sides by 3')).toBeVisible()
    await page.keyboard.press('Escape')
    await expect(sheet).toBeHidden()
    await expect(page.getByRole('button', { name: /x equals 5/, pressed: true })).toBeFocused()
  })
})
