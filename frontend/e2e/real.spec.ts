import { expect, test } from '@playwright/test'
import { expectNoAxeViolations } from './a11y.ts'

// No route mocks: the production build served by FastAPI, with the real packs in
// content/generated. Only GET requests, so no model is called.

const TOPICS = [
  ['negative-numbers', 'Negative numbers'],
  ['fractions', 'Fractions'],
  ['linear-equations', 'Solving linear equations'],
] as const

test('the API lists every topic, and Home links to each', async ({ page, request }) => {
  const res = await request.get('/api/topics?lang=en')
  expect(res.ok()).toBe(true)
  const topics = (await res.json()) as { id: string }[]
  expect(topics.map((x) => x.id).sort()).toEqual(TOPICS.map(([id]) => id).sort())

  await page.goto('/')
  for (const [id, title] of TOPICS) {
    await expect(page.getByRole('link', { name: new RegExp(title) }).first()).toHaveAttribute(
      'href',
      `/topics/${id}`,
    )
  }
})

for (const [id, title] of TOPICS) {
  test(`the real ${id} pack renders`, async ({ page }) => {
    await page.goto(`/topics/${id}`)
    await expect(page.getByRole('heading', { level: 1 })).toHaveText(title)
    await expect(page).toHaveTitle(`${title} · Lesson Coach`)
    const example = page.locator('#example')
    await expect(example.getByRole('button', { pressed: true })).toHaveCount(1)
    await expect(example.locator('[data-math="line"]').first()).toBeVisible()
    await expect(page.locator('#mistakes')).toBeVisible()
    await expectNoAxeViolations(page)
  })
}

test('a real practice problem renders, and Practice reaches it', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('link', { name: 'Practice', exact: true }).click()
  await expect(page).toHaveURL(/\/practice\/[a-z-]+\/1$/)
  await expect(page.getByRole('heading', { level: 1 })).toHaveText(/^Practice: /)
  await expect(page.getByRole('button', { name: 'Show next hint' })).toBeVisible()
  await expectNoAxeViolations(page)
})
