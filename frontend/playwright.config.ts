import { defineConfig, devices } from '@playwright/test'

// Override to run e2e in parallel worktrees: `E2E_PORT=8020 make e2e`. The dev server takes
// E2E_PORT + 1000 unless E2E_DEV_PORT is set, so ports one apart never collide.
/** A port from the environment, or the default; anything else stops the run, naming it. */
function portFrom(name: string, fallback: number): number {
  const raw = process.env[name] ?? String(fallback)
  const port = Number(raw)
  if (!/^\d+$/.test(raw.trim()) || port < 1 || port > 65535)
    throw new Error(`${name} must be a port number from 1 to 65535, got "${raw}"`)
  return port
}
const port = portFrom('E2E_PORT', 8010)
const devPort = portFrom('E2E_DEV_PORT', port + 1000)
const api = `http://127.0.0.1:${port}`
const dev = `http://127.0.0.1:${devPort}`
// BASE_URL runs the app specs against a deployed app instead of local servers, e.g.
// `BASE_URL=https://<app>.azurecontainerapps.io pnpm exec playwright test`.
const remote = process.env.BASE_URL

// The app runs against the production setup: FastAPI serving the built frontend and the API.
// `pnpm e2e` builds first, so the tested dist is always current.
// The dev-only showcases (/demo/math, /demo/input) are not in that build: their specs run
// against the Vite dev server, which proxies /api to the same FastAPI. A deployed app has
// no showcases, so with BASE_URL only the app specs run.
const DEV_SPECS = /(demo|input)\.spec/
// The state matrix runs at five layouts of its own (see e2e/a11y.spec.ts).
const MATRIX = /a11y\.spec/
// Keyboard flows also run at 200% zoom, where the sticky header covers more of the screen.
const ZOOMED = /(a11y|keyboard)\.spec/

export default defineConfig({
  testDir: './e2e',
  // Wakes a scaled-to-zero deployed app; a no-op without BASE_URL.
  globalSetup: './e2e/global-setup.ts',
  reporter: process.env.CI ? 'line' : 'list',
  use: { baseURL: remote ?? api, trace: 'retain-on-failure', reducedMotion: 'reduce' },
  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'] }, testIgnore: [DEV_SPECS, MATRIX] },
    {
      name: 'a11y-desktop',
      use: { ...devices['Desktop Chrome'], viewport: { width: 1280, height: 800 } },
      testMatch: MATRIX,
    },
    // A tablet: the explanation panel is inline (≥768 px) but the section nav is still a strip.
    {
      name: 'a11y-tablet',
      use: { ...devices['Desktop Chrome'], viewport: { width: 820, height: 1180 } },
      testMatch: MATRIX,
    },
    { name: 'a11y-phone', use: { ...devices['Pixel 7'] }, testMatch: MATRIX },
    {
      name: 'a11y-320',
      use: { ...devices['Desktop Chrome'], viewport: { width: 320, height: 800 } },
      testMatch: MATRIX,
    },
    // 200% zoom of a 1280×800 window: CSS sees a 640×400 viewport at twice the pixel density.
    {
      name: 'a11y-zoom200',
      use: {
        ...devices['Desktop Chrome'],
        viewport: { width: 640, height: 400 },
        deviceScaleFactor: 2,
      },
      testMatch: ZOOMED,
    },
    ...(remote
      ? []
      : [
          {
            name: 'dev',
            use: { ...devices['Desktop Chrome'], baseURL: dev },
            testMatch: DEV_SPECS,
          },
          // Touch: the math input on a phone (drawing with touch events, photo upload).
          {
            name: 'mobile',
            use: { ...devices['Pixel 7'], baseURL: dev },
            testMatch: /input\.spec/,
          },
        ]),
  ],
  webServer: remote
    ? undefined
    : [
        {
          command: `cd ../backend && uv run uvicorn app.main:app --host 127.0.0.1 --port ${port}`,
          url: `${api}/api/health`,
          // Never test a server we didn't start: a stale one on this port fails the run.
          reuseExistingServer: false,
          timeout: 120_000,
        },
        {
          command: `API_URL=${api} pnpm exec vite --host 127.0.0.1 --port ${devPort} --strictPort`,
          url: dev,
          reuseExistingServer: false,
          timeout: 120_000,
        },
      ],
})
