import { defineConfig, devices } from '@playwright/test'

const port = 8010
const devPort = 5180
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

export default defineConfig({
  testDir: './e2e',
  // Wakes a scaled-to-zero deployed app; a no-op without BASE_URL.
  globalSetup: './e2e/global-setup.ts',
  reporter: process.env.CI ? 'line' : 'list',
  use: { baseURL: remote ?? api, trace: 'retain-on-failure', reducedMotion: 'reduce' },
  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'] }, testIgnore: DEV_SPECS },
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
