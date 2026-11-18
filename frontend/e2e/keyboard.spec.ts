import { expect, test, type Locator, type Page } from '@playwright/test'
import { expectNoAxeViolations, explainSettled } from './a11y.ts'
import { fixture, mockApi } from './api.ts'

/*
 * Each page's main task done with the keyboard alone: no clicks, no programmatic focus.
 * Every element focus lands on along the way must show a focus indicator (WCAG 2.4.7) and
 * must not be hidden under the sticky header (WCAG 2.4.11).
 */

/** What is wrong with the focused element, or null. Runs in the page. */
function focusProblem(): string | null {
  const el = document.activeElement as HTMLElement | null
  if (!el || el === document.body) return 'nothing focused'
  const name = `${el.tagName.toLowerCase()} "${(el.getAttribute('aria-label') ?? el.textContent ?? '').trim().slice(0, 40)}"`
  const shows = (e: Element) => {
    const s = getComputedStyle(e)
    const outline = s.outlineStyle !== 'none' && parseFloat(s.outlineWidth) > 0
    return outline || s.boxShadow !== 'none'
  }
  // A math field shows its focus on the box around it (a focus-within ring).
  const ring =
    el.tagName === 'MATH-FIELD' ? el.closest<HTMLElement>('[class*="focus-within:ring"]') : el
  if (!ring || !shows(ring)) return `${name}: no visible focus indicator`
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

test('the language picker by keyboard: to Arabic and back', async ({ page }) => {
  await page.goto('/')
  // Its label follows the language, so find it by place.
  const picker = page.locator('header select')
  await tabTo(page, picker)
  const html = page.locator('html')
  for (let i = 0; i < 40 && (await html.getAttribute('lang')) !== 'ar'; i++)
    await page.keyboard.press('ArrowDown')
  await expect(html).toHaveAttribute('dir', 'rtl')
  await expect(picker).toBeFocused()
  for (let i = 0; i < 40 && (await html.getAttribute('lang')) !== 'en'; i++)
    await page.keyboard.press('ArrowUp')
  await expect(html).toHaveAttribute('dir', 'ltr')
})

test.describe('on a phone', () => {
  test.use({ viewport: { width: 390, height: 844 } })

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
