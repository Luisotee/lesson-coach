import { defineConfig, devices } from '@playwright/test'

const port = 8010

// Runs against the production setup: FastAPI serving the built frontend and the API.
// `pnpm e2e` builds first, so the tested dist is always current.
export default defineConfig({
  testDir: './e2e',
  reporter: process.env.CI ? 'line' : 'list',
  use: { baseURL: `http://127.0.0.1:${port}`, trace: 'retain-on-failure', reducedMotion: 'reduce' },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: {
    command: `cd ../backend && uv run uvicorn app.main:app --host 127.0.0.1 --port ${port}`,
    url: `http://127.0.0.1:${port}/api/health`,
    // Never test a server we didn't start: a stale one on this port fails the run.
    reuseExistingServer: false,
    timeout: 120_000,
  },
})
