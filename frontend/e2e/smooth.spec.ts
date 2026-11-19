import { expect, test, type Locator, type Page } from '@playwright/test'
import { typeMath } from './a11y.ts'
import { fixture, mockApi } from './api.ts'

/*
 * Moves within a page scroll smoothly; page changes and reduced motion don't animate.
 * The page's scrollY is recorded every frame while a move runs: a smooth scroll passes through
 * many positions on its way, an instant one jumps straight to the end.
 */

test.beforeEach(async ({ page }) => {
  await mockApi(page, {
    mistake: () => ({ body: fixture('mistake/diagnosed.json') }),
    checkWorking: () => ({ body: fixture('check/bad-line.json') }),
  })
})

/**
 * Records scrollY every frame for `frames` frames, from now. `target` (what will be clicked) is
 * scrolled into view first, since Playwright's click would scroll to it on its own.
 */
async function startRecording(page: Page, frames = 90, target?: Locator) {
  await target?.scrollIntoViewIfNeeded()
  await page.evaluate(() => new Promise(requestAnimationFrame))
  await page.evaluate((frames) => {
    const ys: number[] = []
    ;(window as unknown as { __ys: number[] }).__ys = ys
    const tick = () => {
      ys.push(Math.round(window.scrollY))
      if (ys.length < frames) requestAnimationFrame(tick)
    }
    requestAnimationFrame(tick)
  }, frames)
}

/** Clicks `target`, recording the scroll from just before. */
async function recordClick(page: Page, target: Locator, frames = 90) {
  await startRecording(page, frames, target)
  await target.click()
}

/**
 * The positions passed through on the way, without the start and the end. A smooth scroll
 * passes many; a jump none, or one when the page first shrinks under it on a page change.
 */
async function inBetween(page: Page, frames = 90): Promise<number[]> {
  await page.waitForFunction(
    (frames) => (window as unknown as { __ys: number[] }).__ys.length >= frames,
    frames,
  )
  const ys = await page.evaluate(() => (window as unknown as { __ys: number[] }).__ys)
  const start = ys[0]
  const end = ys.at(-1)
  return [...new Set(ys)].filter((y) => y !== start && y !== end)
}

/** The element's top is below the sticky header (if any), not under it. */
async function expectBelowHeader(page: Page, selector: string) {
  const [top, headerBottom] = await page.evaluate((selector) => {
    const header = document.querySelector('header')!
    const sticky = getComputedStyle(header).position === 'sticky'
    return [
      document.querySelector(selector)!.getBoundingClientRect().top,
      sticky ? header.getBoundingClientRect().bottom : 0,
    ]
  }, selector)
  expect(top).toBeGreaterThanOrEqual(headerBottom - 1)
}

// The suite runs with reduced motion (playwright.config.ts); these ask for motion.
test.describe('with motion', () => {
  test.use({ viewport: { width: 1280, height: 800 }, reducedMotion: 'no-preference' })

  test('home: "Choose a topic" scrolls smoothly to the topic list and focuses it', async ({
    page,
  }) => {
    await page.goto('/')
    await expect(page.getByRole('link', { name: /Solving linear equations/ })).toBeVisible()
    await recordClick(page, page.getByRole('link', { name: 'Choose a topic' }))
    expect((await inBetween(page)).length).toBeGreaterThan(3)
    await expect(page).toHaveURL(/\/#topics$/)
    await expect(page.locator('#topics')).toBeFocused()
    await expectBelowHeader(page, '#topics')
  })

  test('topic: "On this page" links scroll smoothly to their section', async ({ page }) => {
    await page.goto('/topics/linear-equations')
    const nav = page.getByRole('navigation', { name: 'On this page' })
    await recordClick(page, nav.getByRole('link', { name: 'Lesson outline' }))
    expect((await inBetween(page)).length).toBeGreaterThan(3)
    await expect(page).toHaveURL(/#outline$/)
    await expect(page.locator('#outline')).toBeInViewport()
    await expectBelowHeader(page, '#outline')
    // And back up.
    await recordClick(page, nav.getByRole('link', { name: 'The idea' }))
    expect((await inBetween(page)).length).toBeGreaterThan(3)
    await expectBelowHeader(page, '#idea')
  })

  test('a new page starts at its top at once: no animation across pages', async ({ page }) => {
    await page.goto('/topics/linear-equations')
    await page.evaluate(() => window.scrollTo(0, document.documentElement.scrollHeight))
    // The header stays in view (sticky at this size), so the click needs no scroll first.
    const mainNav = page.getByRole('navigation', { name: 'Main' })
    await recordClick(page, mainNav.getByRole('link', { name: 'Topics' }), 30)
    await expect(page.locator('#topics')).toBeFocused()
    // To the topic list of the home page: a page change, so one jump.
    expect((await inBetween(page, 30)).length).toBeLessThanOrEqual(1)

    await page.goto('/topics/linear-equations')
    await page.evaluate(() => window.scrollTo(0, document.documentElement.scrollHeight))
    await recordClick(
      page,
      page.getByRole('navigation', { name: 'Main' }).getByRole('link', { name: 'Practice' }),
      30,
    )
    await expect(page.getByRole('heading', { level: 1 })).toHaveText('Practice: Negative numbers')
    expect((await inBetween(page, 30)).length).toBeLessThanOrEqual(1)
    expect(await page.evaluate(() => window.scrollY)).toBe(0)
  })
})

test.describe('on a phone', () => {
  test.use({ viewport: { width: 390, height: 844 }, reducedMotion: 'no-preference' })

  test('mistake: "Explain this" glides down to the result; "Try another answer" back to the field', async ({
    page,
  }) => {
    await page.goto('/mistake')
    await typeMath(page, 'The problem', '1/2+1/3')
    await typeMath(page, 'What your student answered', '2/5')
    await recordClick(page, page.getByRole('button', { name: 'Explain this' }))
    await expect(page.locator('[data-status="diagnosed"]')).toBeVisible()
    expect((await inBetween(page)).length).toBeGreaterThan(3)
    await expect(page.getByRole('region', { name: 'Result' })).toBeInViewport()

    await recordClick(page, page.getByRole('button', { name: 'Try another answer' }))
    const field = page.locator('math-field[aria-label="What your student answered"]')
    await expect(field).toBeFocused()
    expect((await inBetween(page)).length).toBeGreaterThan(3)
    await expect(field).toBeInViewport()
  })

  test('practice: "Next problem" glides back to the top of the next problem', async ({ page }) => {
    await page.goto('/practice/fractions/1')
    const next = page.getByRole('link', { name: /Next problem/ })
    await recordClick(page, next)
    await expect(page).toHaveURL(/\/practice\/fractions\/2$/)
    expect((await inBetween(page)).length).toBeGreaterThan(3)
    await expect(page.getByRole('heading', { level: 1 })).toBeFocused()
  })
})

test.describe('with reduced motion', () => {
  test.use({ viewport: { width: 1280, height: 800 }, reducedMotion: 'reduce' })

  test('every move is instant', async ({ page }) => {
    await page.goto('/')
    await expect(page.getByRole('link', { name: /Solving linear equations/ })).toBeVisible()
    await recordClick(page, page.getByRole('link', { name: 'Choose a topic' }), 30)
    await expect(page.locator('#topics')).toBeFocused()
    expect((await inBetween(page, 30)).length).toBeLessThanOrEqual(1)
    await expectBelowHeader(page, '#topics')

    await page.goto('/topics/linear-equations')
    await recordClick(
      page,
      page
        .getByRole('navigation', { name: 'On this page' })
        .getByRole('link', { name: 'Lesson outline' }),
      30,
    )
    expect((await inBetween(page, 30)).length).toBeLessThanOrEqual(1)
    await expect(page.locator('#outline')).toBeInViewport()
  })

  test('on a phone, "Explain this" jumps to the result at once', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 })
    await page.goto('/mistake')
    await typeMath(page, 'The problem', '1/2+1/3')
    await typeMath(page, 'What your student answered', '2/5')
    await recordClick(page, page.getByRole('button', { name: 'Explain this' }), 30)
    await expect(page.locator('[data-status="diagnosed"]')).toBeVisible()
    expect((await inBetween(page, 30)).length).toBeLessThanOrEqual(1)
    await expect(page.getByRole('region', { name: 'Result' })).toBeInViewport()
  })
})
