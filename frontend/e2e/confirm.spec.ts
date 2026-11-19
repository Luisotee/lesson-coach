import { expect, test } from '@playwright/test'
import { expectNoAxeViolations, typeMath } from './a11y.ts'
import { mockApi } from './api.ts'
import { drawStroke, mockTranscribe } from './draw.ts'

/*
 * The confirm step where it is used: what was read is checked, used with a button worded for
 * the field, and then shown as the field's value. Nothing is sent before that.
 */

test('mistake: a written problem is checked, used, and sent as confirmed', async ({ page }) => {
  const posted = await mockApi(page)
  await page.goto('/mistake')
  const problem = page.getByRole('group', { name: 'The problem', exact: true })
  await problem.getByRole('tab', { name: 'Write' }).click()
  await drawStroke(page, problem.getByTestId('drawing-canvas'), [30, 30], [90, 50])
  await mockTranscribe(page, [
    { left: '1/2 + 1/2', right: '', op: '', confidence: 0.95, uncertain: false },
  ])
  await problem.getByRole('button', { name: 'Read my writing' }).click()
  await expect(problem.getByRole('heading', { name: 'Check what was read' })).toBeFocused()
  const use = problem.getByRole('button', { name: 'Use this problem' })
  await expect(use).toBeVisible()
  await expect(problem.getByRole('button', { name: 'Draw again' })).toBeVisible()
  await expect(problem.getByRole('button', { name: 'Type it instead' })).toBeVisible()

  // Enter in an edit field ends the edit; it doesn't submit the page's form.
  await problem.getByRole('button', { name: 'Edit line 1' }).click()
  await problem.getByRole('textbox', { name: 'Left side' }).press('Enter')
  await expect(problem.getByRole('textbox', { name: 'Left side' })).toHaveCount(0)
  await expect(page.getByText('Add the problem first.')).toHaveCount(0)
  expect(posted).toHaveLength(0)
  await expectNoAxeViolations(page)

  // Explain before the lines are used: the page asks for that, at the Use button.
  await page.getByRole('button', { name: 'Explain this' }).click()
  await expect(
    problem.getByText('Check what was read, then press “Use this problem”.'),
  ).toBeVisible()
  await expect(use).toBeFocused()
  expect(posted).toHaveLength(0)

  await use.click()
  await expect(
    problem.getByRole('group', { name: 'Confirmed from your handwriting' }),
  ).toBeFocused()
  await expect(problem.getByText('Check what was read')).toHaveCount(0)
  await expectNoAxeViolations(page)

  // The working field words its button for itself.
  const working = page.getByRole('group', { name: 'Their working (optional)', exact: true })
  await working.getByRole('tab', { name: 'Write' }).click()
  await drawStroke(page, working.getByTestId('drawing-canvas'), [30, 30], [90, 50])
  await working.getByRole('button', { name: 'Read my writing' }).click()
  await expect(working.getByRole('button', { name: 'Use this working' })).toBeVisible()
  await working.getByRole('button', { name: 'Draw again' }).click()

  await typeMath(page, 'What your student answered', '2')
  await page.getByRole('button', { name: 'Explain this' }).click()
  await expect.poll(() => posted.length).toBe(1)
  expect(posted[0].body).toMatchObject({ problem: { text: '1/2 + 1/2' }, working: [] })
})

test('practice: written working is used, then checked', async ({ page }) => {
  const posted = await mockApi(page)
  await page.goto('/practice/linear-equations/1')
  const working = page.getByRole('group', { name: 'Your working', exact: true })
  await drawStroke(page, working.getByTestId('drawing-canvas'), [30, 30], [90, 50])
  await mockTranscribe(page, [
    { left: '8*x', right: '56', op: '', confidence: 0.95, uncertain: false },
  ])
  await working.getByRole('button', { name: 'Read my writing' }).click()
  // Read but not used: the page says to use it, and takes focus there.
  await page.getByRole('button', { name: 'Check my working' }).click()
  const useFirst = 'Check what was read, then press “Use this working”.'
  await expect(page.getByText(useFirst)).toBeVisible()
  const use = working.getByRole('button', { name: 'Use this working' })
  await expect(use).toBeFocused()
  expect(posted).toHaveLength(0)

  await use.click()
  await expect(
    working.getByRole('group', { name: 'Confirmed from your handwriting' }),
  ).toBeFocused()
  await expect(page.getByText(useFirst)).toHaveCount(0)
  await expectNoAxeViolations(page)
  await page.getByRole('button', { name: 'Check my working' }).click()
  await expect.poll(() => posted.length).toBe(1)
  expect(posted[0].body).toMatchObject({ lines: [{ left: '8*x', right: '56' }] })
})
