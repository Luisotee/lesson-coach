import { expect, test, type Page } from '@playwright/test'
import { expectNoSideScroll, expectNothingClipped, typeMath } from './a11y.ts'
import { fixture, mockApi } from './api.ts'

/*
 * Print. The topic page prints as a lesson outline (the design's printable view). Practice and
 * Mistake have no print design: they must still print cleanly, without the header and with
 * nothing cut off. Checked at an A4-like width under print media.
 */

test.use({ viewport: { width: 794, height: 1123 } })

test.beforeEach(async ({ page }) => {
  await mockApi(page, { mistake: () => ({ body: fixture('mistake/diagnosed.json') }) })
})

async function print(page: Page) {
  await page.emulateMedia({ media: 'print' })
  await expect(page.locator('header').first()).toBeHidden()
  await expectNoSideScroll(page)
  await expectNothingClipped(page)
}

test('topic: only the title and the timed lesson outline print', async ({ page }) => {
  await page.goto('/topics/linear-equations')
  await expect(page.getByRole('heading', { name: 'Lesson outline' })).toBeVisible()
  await print(page)
  await expect(page.getByRole('heading', { level: 1 })).toBeVisible()
  await expect(page.locator('[data-print]')).toBeVisible()
  await expect(page.locator('[data-print]')).toContainText(/\d+–\d+ min/)
  for (const id of ['idea', 'refresh', 'example', 'mistakes', 'questions'])
    await expect(page.locator(`#${id}`), id).toBeHidden()
  await expect(page.getByRole('navigation', { name: 'On this page' })).toBeHidden()
  await expect(page.getByRole('button', { name: 'Print lesson outline' })).toBeHidden()
})

test('practice prints the problem and hints without the header', async ({ page }) => {
  await page.goto('/practice/linear-equations/1')
  await page.getByRole('button', { name: 'Show next hint' }).click()
  await print(page)
  await expect(page.getByRole('math', { name: '8 x equals 56' }).first()).toBeVisible()
  await expect(page.getByText(/We want the value of/)).toBeVisible()
})

test('a mistake result prints without the header', async ({ page }) => {
  await page.goto('/mistake')
  await typeMath(page, 'The problem', '1/2+1/3')
  await typeMath(page, 'What your student answered', '2/5')
  await page.getByRole('button', { name: 'Explain this' }).click()
  await expect(page.locator('[data-status="diagnosed"]')).toBeVisible()
  await print(page)
  await expect(page.locator('[data-status="diagnosed"]')).toBeVisible()
})
