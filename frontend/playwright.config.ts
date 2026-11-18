import { defineConfig, devices } from '@playwright/test'

const port = 8010

// Runs against the production setup: FastAPI serving the built frontend and the API.
export default defineConfig({
  testDir: './e2e',
  reporter: process.env.CI ? 'line' : 'list',
  use: { baseURL: `http://127.0.0.1:${port}`, trace: 'retain-on-failure' },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: {
    command: `pnpm build && cd ../backend && uv run uvicorn app.main:app --host 127.0.0.1 --port ${port}`,
    url: `http://127.0.0.1:${port}/api/health`,
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
  },
})
