import { expect, test } from '@playwright/test'
import { typeMath } from './a11y.ts'
import { fixture, mockApi } from './api.ts'

/*
 * What a screen reader is given: the accessibility tree of the key parts, as Playwright reads
 * it from Chromium. Templates match in part (listed children, in order), so unrelated
 * additions don't break them. docs/A11Y.md quotes these.
 */

test.beforeEach(async ({ page }) => {
  await mockApi(page, { mistake: () => ({ body: fixture('mistake/diagnosed.json') }) })
})

test('landmarks: skip link, banner with the main nav, main, footer', async ({ page }) => {
  await page.goto('/topics/linear-equations')
  await expect(page.getByRole('heading', { name: 'The idea', exact: true })).toBeVisible()
  await expect(page.locator('body')).toMatchAriaSnapshot(`
    - link "Skip to main content"
    - banner:
      - link "Lesson Coach"
      - navigation "Main":
        - link "Topics"
        - link "A student wrote this"
        - link "Practice"
      - combobox "Language"
    - main:
      - heading "Solving linear equations" [level=1]
      - navigation "On this page"
      - region "The idea"
      - region /3 x plus 5 equals 20/
      - region "What students often get wrong"
      - region "Questions students ask"
      - region "Lesson outline"
    - contentinfo
  `)
})

test('a worked example: each step is a toggle named by its spoken math and the move', async ({
  page,
}) => {
  await page.goto('/topics/linear-equations')
  await expect(page.locator('#example ol').first()).toMatchAriaSnapshot(`
    - list "Worked example 1":
      - listitem:
        - button "3 x plus 5 equals 20; subtract 5 from both sides" [pressed]
      - listitem:
        - button "3 x equals 15; divide both sides by 3"
      - listitem:
        - button "x equals 5"
  `)
})

test('in Arabic the same steps are spoken in Arabic', async ({ page }) => {
  await page.goto('/topics/linear-equations?lng=ar')
  await expect(page.locator('#example ol').first()).toMatchAriaSnapshot(`
    - list "المثال المحلول 1":
      - listitem:
        - button "3 x زائد 5 يساوي 20؛ اطرح 5 من الطرفين" [pressed]
      - listitem:
        - button "3 x يساوي 15؛ اقسم الطرفين على 3"
      - listitem:
        - button "x يساوي 5"
  `)
})

test('hints: opened ones are read, closed ones say so', async ({ page }) => {
  await page.goto('/practice/linear-equations/1')
  await page.getByRole('button', { name: 'Show next hint' }).click()
  await expect(page.getByRole('complementary')).toMatchAriaSnapshot(`
    - complementary "Hints, when you want them":
      - heading "Hints, when you want them" [level=2]
      - button "Start over"
      - list:
        - listitem:
          - text: The goal
          - paragraph:
            - text: We want the value of
            - math "x"
            - text: that makes
            - math "8 x equals 56"
        - listitem: What you need (not opened)
        - listitem: The calculation (not opened)
        - listitem: The answer (not opened)
      - button "Show next hint"
  `)
})

test('a mistake result: the reason, the circled line with its note, what to say', async ({
  page,
}) => {
  await page.goto('/mistake')
  await typeMath(page, 'The problem', '1/2+1/3')
  await typeMath(page, 'What your student answered', '2/5')
  await page.getByRole('button', { name: 'Explain this' }).click()
  await expect(page.getByRole('region', { name: 'Result' })).toMatchAriaSnapshot(`
    - region "Result":
      - heading "To add fractions, add the tops and add the bottoms." [level=2]
      - figure "what they wrote":
        - region "what they wrote":
          - list "what they wrote":
            - listitem:
              - math "one half plus one third"
            - listitem:
              - math /added the bottoms too/
            - listitem:
              - math "equals 2 fifths"
      - figure "the answer, worked out":
        - list "the answer, worked out":
          - listitem:
            - math "one half plus one third"
          - listitem:
            - math "equals 3 sixths plus 2 sixths"
          - listitem:
            - math "equals 5 sixths"
      - heading "What you could say" [level=3]
  `)
})
