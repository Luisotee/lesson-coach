import { expect, test } from '@playwright/test'
import { expectNoAxeViolations, typeMath } from './a11y.ts'
import { fixture, mockApi } from './api.ts'

test.beforeEach(async ({ page }) => {
  await mockApi(page)
})

// Each page's states at every layout, with axe, are in a11y.spec.ts.

test('home lists the topics from the API with their grades', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByRole('link', { name: /Solving linear equations/ })).toBeVisible()
  await expect(page.getByText('Grade 7–8')).toBeVisible()
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
})

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
    // Focus returns to the line now selected, step 3 after Next step.
    await expect(page.getByRole('button', { name: /x equals 5/, pressed: true })).toBeFocused()
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
  // Only the pack's own text is marked English; the UI's headings stay Arabic.
  await expect(page.getByRole('heading', { level: 1 })).toHaveAttribute('lang', 'en')
  const headingLangs = await page
    .locator('main h2')
    .evaluateAll((els) => els.map((el) => el.closest('[lang]')?.getAttribute('lang')))
  expect(new Set(headingLangs)).toEqual(new Set(['ar']))
  await expectNoAxeViolations(page)
})

/** Types into a MathLive field found by its label. */
test('practice: hints, check my working, and previous/next', async ({ page }) => {
  const posted = await mockApi(page, {
    checkWorking: () => ({ body: fixture('check/bad-line.json') }),
  })
  await page.goto('/practice/linear-equations/1')
  await expect(page.getByText('Problem 1 of 8 · just for you, nothing is recorded')).toBeVisible()

  // Check with nothing written: the input says why and takes focus.
  await page.getByRole('button', { name: 'Check my working' }).click()
  await expect(page.getByText('Write or type at least one line first.')).toBeVisible()
  expect(posted).toHaveLength(0)

  await page.getByRole('tab', { name: 'Type' }).click()
  await typeMath(page, 'Your working, line 1', '8x=56')
  await page.getByRole('button', { name: 'Check my working' }).click()
  await expect(page.getByText('Line 2 doesn’t follow from the line before.')).toBeVisible()
  expect(posted[0].url).toBe('/api/check-working')
  expect(posted[0].body).toMatchObject({ problem: { kind: 'solve', text: '8*x = 56' } })
  expect((posted[0].body as { lines: unknown[] }).lines).toHaveLength(1)
  await expectNoAxeViolations(page)
  // The verdict was about that working: changing it drops the verdict.
  await typeMath(page, 'Your working, line 1', '+1')
  await expect(page.getByText('Line 2 doesn’t follow from the line before.')).toHaveCount(0)

  await page.getByRole('button', { name: 'Show next hint' }).click()
  await expect(page.getByText(/We want the value of/)).toBeVisible()

  await page.getByRole('link', { name: 'Next problem' }).click()
  await expect(page).toHaveURL(/\/practice\/linear-equations\/2$/)
  await expect(page.getByText('Problem 2 of 8 · just for you, nothing is recorded')).toBeVisible()
  // A new problem starts fresh: no hints open, no check result.
  await expect(page.getByText(/doesn’t follow/)).toHaveCount(0)
  await page.getByRole('link', { name: 'Previous problem' }).click()
  await expect(page).toHaveURL(/\/practice\/linear-equations\/1$/)
  await expect(page.getByRole('link', { name: 'Previous problem' })).toHaveCount(0)
})

test('practice: a problem number past the pack is not found', async ({ page }) => {
  await page.goto('/practice/linear-equations/9')
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Page not found')
})

const STATES = [
  ['diagnosed', 'To add fractions, add the tops and add the bottoms.'],
  ['correct', 'Your student is right.'],
  ['not-simplified', 'Your student is right.'],
  ['unclear', 'Ask how they got it.'],
  ['slip', 'A slip, not a misunderstanding.'],
  ['out-of-scope', 'This one is outside what the coach covers.'],
] as const

for (const [state, heading] of STATES) {
  test(`mistake: the ${state} result`, async ({ page }) => {
    const posted = await mockApi(page, {
      mistake: () => ({ body: fixture(`mistake/${state}.json`) }),
    })
    await page.goto('/mistake')
    await page.getByRole('button', { name: 'Fractions' }).click()
    await typeMath(page, 'The problem', '2x+6=10')
    await typeMath(page, 'What your student answered', '3')
    await page.getByRole('button', { name: 'Explain this' }).click()
    await expect(page.getByRole('heading', { level: 2, name: heading })).toBeVisible()
    expect(posted[0].body).toMatchObject({
      problem: { latex: expect.stringContaining('x') },
      answer: { latex: '3' },
      topic: 'fractions',
      lang: 'en',
      working: [],
    })
    await expectNoAxeViolations(page)
  })
}

test('mistake: validation, try another answer, and a rate limit', async ({ page }) => {
  let limited = true
  const posted = await mockApi(page, {
    mistake: () =>
      limited
        ? { status: 429, body: { detail: 'Too many requests' }, headers: { 'Retry-After': '2' } }
        : { body: fixture('mistake/diagnosed.json') },
  })
  await page.goto('/mistake')
  await page.getByRole('button', { name: 'Explain this' }).click()
  await expect(page.getByText('Add the problem first.')).toBeVisible()
  await expect(page.getByText('Add your student’s answer.')).toBeVisible()
  expect(posted).toHaveLength(0)

  await typeMath(page, 'The problem', '2x+6=10')
  await typeMath(page, 'What your student answered', '3')
  await page.getByRole('button', { name: 'Explain this' }).click()
  await expect(page.getByRole('alert')).toContainText('Please wait 2 seconds.')
  limited = false
  // Retry stays off until the wait is over.
  await expect(page.getByRole('button', { name: /^Try again in \d s$/ })).toBeDisabled()
  await expect(page.getByRole('button', { name: 'Explain this' })).toBeDisabled()
  await expect(page.getByRole('button', { name: 'Try again', exact: true })).toBeEnabled()
  await page.getByRole('button', { name: 'Try again', exact: true }).click()
  await expect(page.getByText('checked: this rule gives exactly their answer')).toBeVisible()

  await page.getByRole('button', { name: 'Try another answer' }).click()
  await expect(page.locator('math-field[aria-label="What your student answered"]')).toBeFocused()
  await expect(page.getByText('checked: this rule gives exactly their answer')).toHaveCount(0)
})

test('mistake: the result keeps the topic it was asked with and goes when the input changes', async ({
  page,
}) => {
  const posted = await mockApi(page, {
    mistake: () => ({ body: fixture('mistake/diagnosed.json') }),
  })
  await page.goto('/mistake')
  await page.getByRole('button', { name: 'Fractions' }).click()
  await typeMath(page, 'The problem', '1/2+1/3')
  await typeMath(page, 'What your student answered', '2/5')
  await page.getByRole('button', { name: 'Explain this' }).click()
  await expect(page.getByText('try next with your student')).toBeVisible()
  expect(posted[0].body).toMatchObject({ topic: 'fractions' })
  const link = page.getByRole('link', { name: /from the Fractions topic/ })
  await expect(link).toHaveAttribute('href', '/topics/fractions#mistakes')

  // Another chip doesn't relabel a result that came from Fractions.
  await page.getByRole('button', { name: 'Negative numbers' }).click()
  await expect(link).toHaveAttribute('href', '/topics/fractions#mistakes')

  // Changing what the student wrote drops the result, which described the old answer.
  await typeMath(page, 'What your student answered', '1')
  await expect(page.getByText('try next with your student')).toHaveCount(0)
})

test('mistake: the try-next link reaches the section of a topic not yet loaded', async ({
  page,
}) => {
  await mockApi(page, { mistake: () => ({ body: fixture('mistake/diagnosed.json') }) })
  await page.goto('/mistake')
  await page.getByRole('button', { name: 'Fractions' }).click()
  await typeMath(page, 'The problem', '1/2+1/3')
  await typeMath(page, 'What your student answered', '2/5')
  await page.getByRole('button', { name: 'Explain this' }).click()
  await page.getByRole('link', { name: /from the Fractions topic/ }).click()
  await expect(page.locator('#mistakes')).toBeFocused()
  await expect(page.locator('#mistakes')).toBeInViewport()
})

test('topic: opening a #section link directly scrolls to it once the pack loads', async ({
  page,
}) => {
  await page.setViewportSize({ width: 1280, height: 600 })
  await page.goto('/topics/linear-equations#mistakes')
  await expect(page.locator('#mistakes')).toBeInViewport()
  expect(await page.evaluate(() => window.scrollY)).toBeGreaterThan(300)
})

test('practice: switching language keeps the working, the check result and open hints', async ({
  page,
}) => {
  await mockApi(page, { checkWorking: () => ({ body: fixture('check/bad-line.json') }) })
  await page.goto('/practice/linear-equations/1')
  await page.getByRole('tab', { name: 'Type' }).click()
  await typeMath(page, 'Your working, line 1', '8x=56')
  await page.getByRole('button', { name: 'Check my working' }).click()
  await expect(page.locator('[data-check="line_doesnt_follow"]')).toBeVisible()
  await page.getByRole('button', { name: 'Show next hint' }).click()
  await expect(page.getByText(/We want the value of/)).toBeVisible()

  await page.getByLabel('Language').selectOption('ar')
  await expect(page.locator('html')).toHaveAttribute('lang', 'ar')
  await expect(page.locator('[data-check="line_doesnt_follow"]')).toBeVisible()
  await expect(page.getByText(/We want the value of/)).toBeVisible()
  await expect(page.locator('math-field').first()).toHaveJSProperty('value', '8x=56')
})
