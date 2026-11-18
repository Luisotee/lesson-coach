import AxeBuilder from '@axe-core/playwright'
import { expect, test } from '@playwright/test'

test('home page renders, reaches the API and has no axe violations', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByRole('heading', { level: 1, name: 'Lesson Coach' })).toBeVisible()
  await expect(page.getByText('connected')).toBeVisible()
  const results = await new AxeBuilder({ page })
    .withTags(['wcag2a', 'wcag2aa', 'wcag22aa'])
    .analyze()
  expect(results.violations).toEqual([])
})

test('client routes fall back to the app', async ({ page }) => {
  await page.goto('/topics/fractions')
  await expect(page.getByRole('heading', { level: 1, name: 'Lesson Coach' })).toBeVisible()
})
