import { test, type Locator, type Page, type Request } from '@playwright/test'

/** Answers /api/transcribe with the given lines, and keeps each request for inspection. */
export async function mockTranscribe(page: Page, lines: object[], status = 200) {
  const requests: Request[] = []
  await page.route('**/api/transcribe', async (route) => {
    requests.push(route.request())
    if (status !== 200) return route.fulfill({ status, body: '' })
    await route.fulfill({ json: { status: 'ok', reason: null, lines } })
  })
  return requests
}

/** Draws a short stroke with touch on a touch device, else with the mouse. */
export async function drawStroke(
  page: Page,
  canvas: Locator,
  from: [number, number],
  to: [number, number],
) {
  await canvas.scrollIntoViewIfNeeded()
  const box = (await canvas.boundingBox())!
  const pts = Array.from({ length: 8 }, (_, i) => ({
    x: box.x + from[0] + ((to[0] - from[0]) * i) / 7,
    y: box.y + from[1] + ((to[1] - from[1]) * i) / 7,
  }))
  if (test.info().project.use.hasTouch) {
    const cdp = await page.context().newCDPSession(page)
    await cdp.send('Input.dispatchTouchEvent', { type: 'touchStart', touchPoints: [pts[0]] })
    for (const p of pts.slice(1))
      await cdp.send('Input.dispatchTouchEvent', { type: 'touchMove', touchPoints: [p] })
    await cdp.send('Input.dispatchTouchEvent', { type: 'touchEnd', touchPoints: [] })
    await cdp.detach()
  } else {
    await page.mouse.move(pts[0].x, pts[0].y)
    await page.mouse.down()
    for (const p of pts.slice(1)) await page.mouse.move(p.x, p.y)
    await page.mouse.up()
  }
}
