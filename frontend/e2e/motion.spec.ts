import { expect, test, type Page } from '@playwright/test'
import { typeMath } from './a11y.ts'
import { fixture, mockApi } from './api.ts'

/*
 * prefers-reduced-motion on the real pages (the write-on itself is tested on /demo/math, the
 * only place that writes lines on). Under `reduce` no CSS animation runs at all (the hero's
 * float, the marker under a chosen line, the circle drawn around a mistake, spinners) and
 * nothing loops. Motion may still fade opacity, which WCAG 2.3.3 allows.
 */

/** The page's running animations: CSS ones by name, and any that loop forever. */
async function animations(page: Page) {
  return page.evaluate(() => {
    const all = document.getAnimations()
    return {
      css: all
        .filter((a): a is CSSAnimation => a instanceof CSSAnimation)
        .map((a) => a.animationName),
      looping: all.filter((a) => a.effect?.getTiming().iterations === Infinity).length,
    }
  })
}

/** Home, a chosen step, a circled mistake and a checked line: every animated thing we have. */
async function visitAnimatedStates(page: Page, check: (where: string) => Promise<void>) {
  await mockApi(page, {
    mistake: () => ({ body: fixture('mistake/diagnosed.json') }),
    checkWorking: () => ({ body: fixture('check/bad-line.json') }),
  })
  await page.goto('/')
  await expect(page.getByRole('link', { name: /Solving linear equations/ })).toBeVisible()
  await check('home')

  await page.goto('/topics/linear-equations')
  await page.getByRole('button', { name: /3 x equals 15/ }).click()
  await page.getByRole('tab', { name: 'Picture' }).click()
  await expect(page.locator('[data-picture="balance"]')).toBeVisible()
  await check('topic, a step chosen, its picture')

  await page.goto('/mistake')
  await typeMath(page, 'The problem', '1/2+1/3')
  await typeMath(page, 'What your student answered', '2/5')
  await page.getByRole('button', { name: 'Explain this' }).click()
  await expect(page.locator('[data-mark="circle"]').first()).toBeVisible()
  await check('mistake, the answer circled')
}

test('under reduced motion nothing animates by CSS and nothing loops', async ({ page }) => {
  await visitAnimatedStates(page, async (where) => {
    expect(await animations(page), where).toEqual({ css: [], looping: 0 })
  })
})

test.describe('without reduced motion', () => {
  test.use({ reducedMotion: 'no-preference' })

  test('the same states do animate, so the check above means something', async ({ page }) => {
    const seen = new Set<string>()
    await visitAnimatedStates(page, async () => {
      for (const name of (await animations(page)).css) seen.add(name)
    })
    expect([...seen]).toEqual(expect.arrayContaining(['floaty', 'marker', 'draw']))
  })
})
