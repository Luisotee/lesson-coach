import fs from 'node:fs'
import path from 'node:path'
import { expect, test, type Page } from '@playwright/test'
import { chooseLanguage, expectNoAxeViolations, t } from './a11y.ts'
import { drawStroke, mockTranscribe } from './draw.ts'

const FIXTURE = path.join(import.meta.dirname, 'fixtures', 'working.jpg')

const card = (page: Page, heading: string) =>
  page.locator('section', { has: page.getByRole('heading', { level: 2, name: heading }) })

test.beforeEach(async ({ page }) => {
  await page.goto('/demo/input')
  await expect(page.locator('math-field')).toHaveCount(2)
})

test('the input demo has no axe violations', async ({ page }) => {
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Math input components')
  await expectNoAxeViolations(page)
})

test('typing 1/2 gives a stacked fraction and hands LaTeX to the page', async ({ page }) => {
  const expression = card(page, 'One expression')
  const field = expression.locator('math-field')
  await field.focus()
  await page.keyboard.type('1/')
  // An empty denominator isn't sent.
  await expect(expression.getByText('Fill in the empty box first.')).toBeVisible()
  await expect(expression.getByTestId('received')).toHaveText('Nothing yet.')
  await page.keyboard.type('2')
  await expect(field.locator('.ML__mfrac')).toBeVisible()
  await expect(expression.getByTestId('received')).toHaveText(
    '{"mode":"type","math":{"latex":"\\\\frac12"}}',
  )
  await expect(expression.locator('math-field')).toHaveAttribute('aria-label', 'The problem')
})

test('the tabs work from the keyboard alone', async ({ page }) => {
  const expression = card(page, 'One expression')
  await expression.getByRole('tab', { name: 'Type' }).focus()
  await page.keyboard.press('ArrowRight')
  await expect(expression.getByRole('tab', { name: 'Write' })).toHaveAttribute(
    'aria-selected',
    'true',
  )
  await page.keyboard.press('ArrowRight')
  await expect(expression.getByRole('tab', { name: 'Photo' })).toBeFocused()
  await expect(expression.getByRole('button', { name: 'Take a photo' })).toBeVisible()
  // Tab moves into the panel, where typing is always offered.
  await page.keyboard.press('Tab')
  await page.keyboard.press('Tab')
  await page.keyboard.press('Tab')
  await page.keyboard.press('Tab')
  await expect(expression.getByRole('button', { name: 'Type it instead' })).toBeFocused()
  await page.keyboard.press('Enter')
  await expect(expression.getByRole('tab', { name: 'Type' })).toHaveAttribute(
    'aria-selected',
    'true',
  )
  await expect(expression.locator('math-field')).toBeFocused()
  await page.keyboard.type('3/4')
  await expect(expression.getByTestId('received')).toContainText('\\\\frac34')
})

test('draw, undo, redo, clear, then read and confirm the working', async ({ page }) => {
  const working = card(page, 'Lines of working')
  const canvas = working.getByTestId('drawing-canvas')
  await drawStroke(page, canvas, [30, 40], [90, 60])
  await drawStroke(page, canvas, [120, 40], [160, 90])
  await expect(canvas).toHaveAttribute('aria-label', /2 strokes/)
  await working.getByRole('button', { name: 'Undo' }).click()
  await expect(canvas).toHaveAttribute('aria-label', /1 stroke$/)
  await working.getByRole('button', { name: 'Redo' }).click()
  await expect(canvas).toHaveAttribute('aria-label', /2 strokes/)
  await working.getByRole('button', { name: 'Clear' }).click()
  await expect(canvas).toHaveAttribute('aria-label', /empty/)
  await expect(working.getByRole('status').filter({ hasText: 'Cleared.' })).toBeAttached()
  await working.getByRole('button', { name: 'Undo' }).click()
  await expect(canvas).toHaveAttribute('aria-label', /2 strokes/)

  const requests = await mockTranscribe(page, [
    { left: '2*x + 6', right: '10', op: '-6', confidence: 0.96, uncertain: false },
    { left: '2*x', right: '4', op: '', confidence: 0.5, uncertain: true },
  ])
  await working.getByRole('button', { name: 'Read my writing' }).click()
  await expect(working.getByRole('heading', { name: 'Check what was read' })).toBeFocused()
  expect(requests).toHaveLength(1)
  expect(requests[0].headers()['content-type']).toMatch(/^multipart\/form-data/)
  expect(requests[0].postDataBuffer()!.includes(Buffer.from('Content-Type: image/png'))).toBe(true)
  await expect(working.getByText('1 line needs a check.')).toBeVisible()
  await expect(working.getByTestId('received')).toHaveText('Nothing yet.')
  await expectNoAxeViolations(page)

  await working.getByRole('button', { name: 'Edit line 2' }).click()
  await working.getByRole('textbox', { name: 'Right side (after =)' }).fill('5')
  await working.getByRole('button', { name: 'Done editing line 2' }).click()
  await expectNoAxeViolations(page)
  await working.getByRole('button', { name: 'Use these lines' }).click()
  const received =
    '{"mode":"write","lines":[{"left":"2*x + 6","right":"10","op":"-6"},{"left":"2*x","right":"5"}]}'
  await expect(working.getByTestId('received')).toHaveText(received)

  // Set: the math is the field's value, in ink, focused, with Change.
  const set = working.getByRole('group', { name: 'Confirmed from your handwriting' })
  await expect(set).toBeFocused()
  await expect(set.locator('[data-pen="ink"]')).toBeVisible()
  await expect(working.getByRole('heading', { name: 'Check what was read' })).toHaveCount(0)
  await expectNoAxeViolations(page)

  // Change takes the value back until the lines are used again.
  await set.getByRole('button', { name: /^Change / }).click()
  await expect(working.getByRole('heading', { name: 'Check what was read' })).toBeFocused()
  await expect(working.getByTestId('received')).toHaveText('Nothing yet.')
  await working.getByRole('button', { name: 'Use these lines' }).click()
  await expect(working.getByTestId('received')).toHaveText(received)
})

test('a photo is cropped, turned, stripped of EXIF and read', async ({ page }) => {
  const working = card(page, 'Lines of working')
  await working.getByRole('tab', { name: 'Photo' }).click()
  await working.getByTestId('photo-upload').setInputFiles(FIXTURE)
  const cropBox = working.getByTestId('crop-box')
  await expect(cropBox).toBeVisible()
  await expectNoAxeViolations(page)

  await cropBox.focus()
  const before = (await cropBox.boundingBox())!
  await page.keyboard.press('ArrowRight')
  await expect.poll(async () => (await cropBox.boundingBox())!.x).toBeGreaterThan(before.x)
  await page.keyboard.press('Shift+ArrowUp')
  await expect.poll(async () => (await cropBox.boundingBox())!.height).toBeLessThan(before.height)

  // The fixture is landscape; a quarter turn makes it portrait.
  const photo = working.getByRole('img', { name: 'Your photo' })
  const wide = (await photo.boundingBox())!
  expect(wide.width).toBeGreaterThan(wide.height)
  await working.getByRole('button', { name: 'Turn 90°' }).click()
  await expect
    .poll(async () => {
      const b = (await photo.boundingBox())!
      return b.height > b.width
    })
    .toBe(true)
  await working.getByRole('button', { name: 'Turn 90°' }).click()
  await working.getByRole('button', { name: 'Turn 90°' }).click()
  await working.getByRole('button', { name: 'Turn 90°' }).click()

  const requests = await mockTranscribe(page, [
    { left: '2*x + 6', right: '10', op: '', confidence: 0.9, uncertain: false },
  ])
  await working.getByRole('button', { name: 'Read this part' }).click()
  await expect(working.getByRole('heading', { name: 'Check what was read' })).toBeVisible()
  const body = requests[0].postDataBuffer()!
  expect(body.includes(Buffer.from('Content-Type: image/jpeg'))).toBe(true)
  expect(body.includes(Buffer.from('Exif'))).toBe(false)
  expect(body.includes(Buffer.from('FixtureCam'))).toBe(false)
  expect(body.length).toBeLessThan(5 * 1024 * 1024)
  await expect(working.getByRole('img', { name: 'The cropped photo that was read' })).toBeVisible()
  await expectNoAxeViolations(page)
  await working.getByRole('button', { name: 'Use these lines' }).click()
  await expect(working.getByTestId('received')).toHaveText(
    '{"mode":"photo","lines":[{"left":"2*x + 6","right":"10"}]}',
  )
  await expect(working.getByRole('group', { name: 'Confirmed from the photo' })).toBeFocused()
})

test('when reading fails, the error is honest and typing is one step away', async ({ page }) => {
  const expression = card(page, 'One expression')
  await expression.getByRole('tab', { name: 'Write' }).click()
  await drawStroke(page, expression.getByTestId('drawing-canvas'), [30, 30], [80, 60])
  await mockTranscribe(page, [], 503)
  await expression.getByRole('button', { name: 'Read my writing' }).click()
  const alert = expression.getByRole('alert')
  await expect(alert).toHaveText(/Reading isn’t available right now/)
  await expect(alert).toBeFocused()
  await expect(expression.getByTestId('received')).toHaveText('Nothing yet.')
  await expectNoAxeViolations(page)
  await expression.getByRole('button', { name: 'Type it instead' }).click()
  await expect(expression.locator('math-field')).toBeFocused()
})

test('in Arabic the page is right to left and the math stays left to right', async ({ page }) => {
  await chooseLanguage(page, 'العربية')
  await expect(page.locator('html')).toHaveAttribute('dir', 'rtl')
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('مكوّنات إدخال الرياضيات')
  const field = page.locator('math-field').first()
  await expect(field.locator('xpath=ancestor::*[@dir][1]')).toHaveAttribute('dir', 'ltr')
  await expect(
    page.getByTestId('drawing-canvas').first().locator('xpath=ancestor::*[@dir][1]'),
  ).toHaveAttribute('dir', 'ltr')
  await expectNoAxeViolations(page)
})

test('MathLive is not in the main bundle', async () => {
  test.skip(test.info().project.name !== 'chromium', 'one check is enough')
  const dist = path.join(import.meta.dirname, '..', 'dist')
  const html = fs.readFileSync(path.join(dist, 'index.html'), 'utf8')
  const entry = /<script type="module"[^>]*src="\/([^"]+)"/.exec(html)![1]
  const main = fs.readFileSync(path.join(dist, entry), 'utf8')
  expect(main).not.toContain('ML__') // MathLive's own class prefix
  expect(fs.readdirSync(path.join(dist, 'assets')).some((f) => f.startsWith('mathlive'))).toBe(true)
})

test('a photo that cannot be opened does not take focus from typing elsewhere', async ({
  page,
}) => {
  const expression = card(page, 'One expression')
  await expression.getByRole('tab', { name: 'Photo' }).click()
  await expression.getByTestId('photo-upload').setInputFiles({
    name: 'bad.png',
    mimeType: 'image/png',
    buffer: Buffer.from('not an image'),
  })
  await expect(expression.getByRole('alert')).toHaveText(/This photo couldn’t be opened/)
  const working = card(page, 'Lines of working')
  await working.getByRole('tab', { name: 'Type' }).click()
  const field = working.locator('math-field').first()
  await field.focus()
  await page.keyboard.type('x+12')
  await expect(working.getByTestId('received')).toHaveText(
    '{"mode":"type","lines":[{"latex":"x+12"}]}',
  )
  await expect(field).toBeFocused()
})

test('Add a line moves focus to the new line', async ({ page }) => {
  const working = card(page, 'Lines of working')
  await working.getByRole('tab', { name: 'Type' }).click()
  await working.locator('math-field').first().focus()
  await page.keyboard.type('2x=4')
  await working.getByRole('button', { name: 'Add a line' }).click()
  const second = working.locator('math-field').nth(1)
  await expect(second).toBeFocused()
  await page.keyboard.type('x=2')
  await expect(working.getByTestId('received')).toHaveText(
    '{"mode":"type","lines":[{"latex":"2x=4"},{"latex":"x=2"}]}',
  )
})

test('the board is locked while the drawing is being read', async ({ page }) => {
  const working = card(page, 'Lines of working')
  const canvas = working.getByTestId('drawing-canvas')
  await drawStroke(page, canvas, [30, 40], [90, 60])
  let release: () => void = () => {}
  const held = new Promise<void>((r) => (release = r))
  await page.route('**/api/transcribe', async (route) => {
    await held
    await route.fulfill({
      json: {
        status: 'ok',
        reason: null,
        lines: [{ left: 'x', right: '2', op: '', confidence: 0.9, uncertain: false }],
      },
    })
  })
  await working.getByRole('button', { name: 'Read my writing' }).click()
  await expect(working.getByText('Reading your writing…')).toBeVisible()
  await drawStroke(page, canvas, [120, 40], [160, 90])
  await expect(canvas).toHaveAttribute('aria-label', /1 stroke$/)
  await expect(working.getByRole('button', { name: 'Undo' })).toHaveAttribute(
    'aria-disabled',
    'true',
  )
  release()
  await expect(working.getByRole('heading', { name: 'Check what was read' })).toBeVisible()
})

test('one fast stroke is drawn on the screen at once', async ({ page }) => {
  const canvas = card(page, 'Lines of working').getByTestId('drawing-canvas')
  await canvas.scrollIntoViewIfNeeded()
  // Down, ten moves and up in one task: the release lands in the same frame as the last move.
  const ink = await canvas.evaluate(async (el: HTMLCanvasElement) => {
    const box = el.getBoundingClientRect()
    const at = (type: string, i: number) =>
      el.dispatchEvent(
        new PointerEvent(type, {
          pointerId: 1,
          pointerType: 'mouse',
          button: 0,
          bubbles: true,
          clientX: box.left + 30 + i * 12,
          clientY: box.top + 40,
        }),
      )
    at('pointerdown', 0)
    for (let i = 1; i <= 10; i++) at('pointermove', i)
    at('pointerup', 10)
    await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)))
    const data = el.getContext('2d')!.getImageData(0, 0, el.width, el.height).data
    let n = 0
    for (let i = 3; i < data.length; i += 4) if (data[i] > 0) n++
    return n
  })
  expect(ink).toBeGreaterThan(100)
})

test('a failed photo read keeps the photo to try again', async ({ page }) => {
  const working = card(page, 'Lines of working')
  await working.getByRole('tab', { name: 'Photo' }).click()
  await working.getByTestId('photo-upload').setInputFiles(FIXTURE)
  let calls = 0
  await page.route('**/api/transcribe', async (route) => {
    calls++
    if (calls === 1) return route.fulfill({ status: 503, body: '' })
    await route.fulfill({
      json: {
        status: 'ok',
        reason: null,
        lines: [{ left: 'x', right: '2', op: '', confidence: 0.9, uncertain: false }],
      },
    })
  })
  await working.getByRole('button', { name: 'Read this part' }).click()
  await expect(working.getByRole('alert')).toHaveText(/Reading isn’t available right now/)
  await expect(working.getByTestId('crop-box')).toBeVisible()
  await expectNoAxeViolations(page)
  await working.getByRole('button', { name: 'Try again' }).click()
  await expect(working.getByRole('heading', { name: 'Check what was read' })).toBeVisible()
  expect(calls).toBe(2)
})

/*
 * MathLive's on-screen keyboard (touch only) marks its selected layer tab in an accent colour,
 * which index.css sets. That tab must read at 4.5:1 against the keyboard behind it in both
 * colour schemes: MathLive draws a dark keyboard when the OS is in dark mode.
 */
for (const colorScheme of ['light', 'dark'] as const) {
  test.describe(`the on-screen keyboard in ${colorScheme} mode`, () => {
    test.use({ colorScheme })

    test('its selected tab has enough contrast', async ({ page }) => {
      test.skip(!test.info().project.use.hasTouch, 'the keyboard opens on touch devices')
      await page.locator('math-field').first().tap()
      const tab = page.locator('.ML__keyboard .MLK__tooltip.selected').filter({ visible: true })
      await expect(tab.first()).toBeVisible()
      const ratio = await tab.first().evaluate((el) => {
        const rgb = (c: string) => (c.match(/[\d.]+/g) ?? []).map(Number)
        const lum = (c: string) => {
          const [r, g, b] = rgb(c).map((v) => v / 255)
          const f = (v: number) => (v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4)
          return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)
        }
        // The nearest box behind the tab that paints a solid background.
        let back: Element | null = el
        while (back && rgb(getComputedStyle(back).backgroundColor)[3] !== undefined)
          back = back.parentElement
        if (!back) throw new Error('no solid background behind the tab')
        const [a, b] = [
          lum(getComputedStyle(el).color),
          lum(getComputedStyle(back).backgroundColor),
        ]
        return (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05)
      })
      expect(ratio).toBeGreaterThanOrEqual(4.5)
    })
  })
}

test('in Arabic the confirmed math stays left to right', async ({ page }) => {
  await chooseLanguage(page, 'العربية')
  await expect(page.locator('html')).toHaveAttribute('dir', 'rtl')
  const working = page.locator('section', {
    has: page.getByRole('heading', { level: 2, name: t('ar', 'demo.inputLines') }),
  })
  await working.getByRole('tab', { name: t('ar', 'input.mode.write') }).click()
  await drawStroke(page, working.getByTestId('drawing-canvas'), [30, 30], [90, 50])
  await mockTranscribe(page, [
    { left: '2*x + 6', right: '10', op: '-6', confidence: 0.95, uncertain: false },
  ])
  await working.getByRole('button', { name: t('ar', 'input.write.read') }).click()
  await expect(
    working.getByRole('heading', { name: t('ar', 'input.review.heading') }),
  ).toBeVisible()
  await expectNoAxeViolations(page)
  await working.getByRole('button', { name: t('ar', 'input.review.useLines') }).click()
  const set = working.getByRole('group', { name: t('ar', 'input.set.fromWrite') })
  await expect(set).toBeFocused()
  await expect(set.locator('[data-pen]')).toHaveAttribute('dir', 'ltr')
  await expectNoAxeViolations(page)
})
