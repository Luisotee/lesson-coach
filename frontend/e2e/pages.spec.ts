import AxeBuilder from '@axe-core/playwright'
import { expect, test, type Page } from '@playwright/test'
import { mockApi } from './api.ts'

const AXE_TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa']
const WIDTHS = [320, 768, 1440] as const

async function expectNoAxeViolations(page: Page) {
  const results = await new AxeBuilder({ page }).withTags(AXE_TAGS).analyze()
  expect(results.violations).toEqual([])
}

async function expectNoSideScroll(page: Page) {
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
  )
  expect(overflow).toBeLessThanOrEqual(0)
}

test.beforeEach(async ({ page }) => {
  await mockApi(page)
})

for (const width of WIDTHS) {
  test.describe(`at ${width} px`, () => {
    test.use({ viewport: { width, height: 900 } })

    test('home lists the topics from the API', async ({ page }) => {
      await page.goto('/')
      await expect(page.getByRole('link', { name: /Solving linear equations/ })).toBeVisible()
      await expect(page.getByText('Grade 7–8')).toBeVisible()
      await expectNoSideScroll(page)
      await expectNoAxeViolations(page)
    })

    test('topic page renders every section', async ({ page }) => {
      await page.goto('/topics/linear-equations')
      await expect(
        page.getByRole('heading', { level: 1, name: 'Solving linear equations' }),
      ).toBeVisible()
      for (const name of [
        'The idea',
        'Why it works',
        'What students often get wrong',
        'Questions students ask',
        'Lesson outline',
      ]) {
        await expect(page.getByRole('heading', { name, exact: true })).toBeVisible()
      }
      await expectNoSideScroll(page)
      await expectNoAxeViolations(page)
    })
  })
}

test('topic: selecting a line and switching explanation modes', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.goto('/topics/linear-equations')
  const second = page.getByRole('button', { name: /3 x equals 15/ })
  await second.click()
  await expect(second).toHaveAttribute('aria-pressed', 'true')
  await expect(page.getByText('Step 2 · subtract 5 from both sides')).toBeVisible()
  await expect(page.getByText(/Taking 5 from only one side/)).toBeVisible()
  await page.getByRole('tab', { name: 'Another way' }).click()
  await expect(page.getByText(/Undo the last thing/)).toBeVisible()
  await page.getByRole('tab', { name: 'Picture' }).click()
  await expect(page.locator('[data-picture="balance"]')).toBeVisible()
  await expect(page.getByText(/Remove 5 from each pan/)).toBeVisible()
  // Keyboard: arrow keys move between the tabs.
  await page.getByRole('tab', { name: 'Picture' }).focus()
  await page.keyboard.press('ArrowLeft')
  await expect(page.getByRole('tab', { name: 'Another way' })).toHaveAttribute(
    'aria-selected',
    'true',
  )
  await expectNoAxeViolations(page)
})

test('topic: previous and next worked example, and the check line', async ({ page }) => {
  await page.goto('/topics/linear-equations')
  await expect(page.getByRole('math', { name: /3 times 5 plus 5 equals 20/ })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Previous worked example' })).toBeDisabled()
  await page.getByRole('button', { name: 'Next worked example' }).click()
  await expect(page.getByText('worked example 2 of 3')).toBeVisible()
  await expect(page.getByRole('heading', { name: /Solve.*2 x plus 6 equals 10/ })).toBeVisible()
  await page.getByRole('button', { name: 'Next worked example' }).click()
  await expect(page.getByRole('button', { name: 'Next worked example' })).toBeDisabled()
  await page.getByRole('button', { name: 'Previous worked example' }).click()
  await expect(page.getByText('worked example 2 of 3')).toBeVisible()
})

test.describe('topic on a phone', () => {
  test.use({ viewport: { width: 390, height: 844 } })
  test('a line opens the explanation in a bottom sheet with previous and next step', async ({
    page,
  }) => {
    await page.goto('/topics/linear-equations')
    await page.getByRole('button', { name: /3 x equals 15/ }).click()
    const sheet = page.getByRole('dialog')
    await expect(sheet).toBeVisible()
    await expect(sheet.getByText('Step 2 · subtract 5 from both sides')).toBeVisible()
    await sheet.getByRole('button', { name: 'Next step' }).click()
    await expect(sheet.getByText('Step 3 · divide both sides by 3')).toBeVisible()
    await expect(sheet.getByRole('button', { name: 'Next step' })).toBeDisabled()
    await sheet.getByRole('tab', { name: 'Picture' }).click()
    await expect(sheet.locator('[data-picture="balance"]')).toBeVisible()
    await expectNoAxeViolations(page)
    await page.keyboard.press('Escape')
    await expect(sheet).toBeHidden()
  })
})

test('topic: refresh-first links, accordion, Akelius and practice links', async ({ page }) => {
  await page.goto('/topics/linear-equations')
  const q2 = page.getByRole('button', { name: /Can I just move the 5/ })
  await expect(q2).toHaveAttribute('aria-expanded', 'false')
  await q2.click()
  await expect(q2).toHaveAttribute('aria-expanded', 'true')
  await expect(page.getByText(/is a shortcut for subtracting 5/)).toBeVisible()
  const akelius = page.getByRole('link', { name: /two-step equations/ })
  await expect(akelius).toHaveAttribute('href', 'https://akelius.education/math/en/lesson/22124')
  await expect(akelius).toHaveAttribute('target', '_blank')
  await page.getByRole('link', { name: 'Fractions', exact: true }).click()
  await expect(page.getByRole('heading', { level: 1, name: 'Fractions' })).toBeVisible()
  await page.getByRole('link', { name: /Try these problems yourself first/ }).click()
  await expect(page).toHaveURL(/\/practice\/fractions\/1$/)
})

test('topic: the section nav marks the section in view', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.goto('/topics/linear-equations')
  const nav = page.getByRole('navigation', { name: 'On this page' })
  await nav.getByRole('link', { name: 'Lesson outline' }).click()
  await expect(nav.getByRole('link', { name: 'Lesson outline' })).toHaveAttribute(
    'aria-current',
    'true',
  )
})

test('topic: print shows only the title and the lesson outline', async ({ page }) => {
  await page.goto('/topics/linear-equations')
  await expect(page.getByRole('button', { name: 'Print lesson outline' })).toBeVisible()
  await page.emulateMedia({ media: 'print' })
  await expect(page.getByRole('heading', { level: 1 })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Lesson outline' })).toBeVisible()
  await expect(page.getByText('Model it')).toBeVisible()
  for (const hidden of ['The idea', 'What students often get wrong', 'Questions students ask']) {
    await expect(page.getByRole('heading', { name: hidden, exact: true })).toBeHidden()
  }
  await expect(page.locator('header').first()).toBeHidden()
})

test('topic: an unknown topic is not found; a server error offers a retry', async ({ page }) => {
  await page.goto('/topics/algebra')
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Page not found')
  let failing = true
  await page.route('**/api/topics/fractions**', (route) =>
    failing ? route.fulfill({ status: 500, body: '{}' }) : route.fallback(),
  )
  await page.goto('/topics/fractions')
  await expect(page.getByRole('alert')).toContainText('This couldn’t be loaded.')
  failing = false
  await page.getByRole('button', { name: 'Try again' }).click()
  await expect(page.getByRole('heading', { name: 'The idea', exact: true })).toBeVisible()
})

test('topic in Arabic: RTL page, math stays left to right, English pack marked', async ({
  page,
}) => {
  await page.goto('/topics/linear-equations?lng=ar')
  await expect(page.locator('html')).toHaveAttribute('dir', 'rtl')
  await expect(page.getByText('معروض بالإنجليزية: لم يُترجم بعد')).toBeVisible()
  const dirs = await page
    .locator('[role="math"]')
    .evaluateAll((els) => els.map((el) => getComputedStyle(el).direction))
  expect(new Set(dirs)).toEqual(new Set(['ltr']))
  await expectNoAxeViolations(page)
})
