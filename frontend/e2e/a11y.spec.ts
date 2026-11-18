import { expect, test, type Page } from '@playwright/test'
import {
  checkState,
  expectNoAxeViolations,
  expectNoSideScroll,
  expectNothingClipped,
  typeMath,
} from './a11y.ts'
import { fixture, mockApi, type ApiOverrides } from './api.ts'

/*
 * Every page in every state, each checked for zero axe violations (WCAG 2.2 AA), no sideways
 * page scroll and no clipped text. playwright.config.ts runs this file at four layouts:
 * desktop 1280 px, a phone (Pixel 7, touch), 320 px, and 200% zoom (a 1280×800 window at
 * 200% is a 640×400 CSS viewport). The API is the fixture API; nothing calls a model.
 */

/** A route that never answers, to hold a page in its loading state. */
async function hold(page: Page, url: string) {
  await page.route(url, () => new Promise(() => {}))
}

async function failWith(page: Page, url: string, status: number, headers = {}) {
  await page.route(url, (route) =>
    route.fulfill({ status, contentType: 'application/json', headers, body: '{}' }),
  )
}

async function explain(page: Page, overrides: ApiOverrides) {
  await mockApi(page, overrides)
  await page.goto('/mistake')
  await page.getByRole('button', { name: 'Fractions' }).click()
  await typeMath(page, 'The problem', '1/2+1/3')
  await typeMath(page, 'What your student answered', '2/5')
  await page.getByRole('button', { name: 'Explain this' }).click()
}

async function checkWorking(page: Page, result: string | { status: number }) {
  await mockApi(page, {
    checkWorking: () =>
      typeof result === 'string' ? { body: fixture(result) } : { status: result.status, body: {} },
  })
  await page.goto('/practice/linear-equations/1')
  await page.getByRole('tab', { name: 'Type' }).click()
  await typeMath(page, 'Your working, line 1', '8x=56')
  await page.getByRole('button', { name: 'Check my working' }).click()
}

const showHints = async (page: Page, n: number) => {
  await mockApi(page)
  await page.goto('/practice/linear-equations/1')
  for (let i = 0; i < n; i++)
    await page.getByRole('button', { name: /Show next hint|Show the answer/ }).click()
}

const STATES: [string, (page: Page) => Promise<void>][] = [
  // Home
  [
    'home: loading',
    async (page) => {
      await hold(page, '**/api/topics?**')
      await page.goto('/')
      await expect(page.locator('[data-state="loading"]')).toBeVisible()
    },
  ],
  [
    'home: loaded',
    async (page) => {
      await mockApi(page)
      await page.goto('/')
      await expect(page.getByRole('link', { name: /Solving linear equations/ })).toBeVisible()
    },
  ],
  [
    'home: topics failed',
    async (page) => {
      await failWith(page, '**/api/topics?**', 500)
      await page.goto('/')
      await expect(page.getByRole('alert')).toBeVisible({ timeout: 15_000 })
    },
  ],
  // Topic
  [
    'topic: loading',
    async (page) => {
      // Registered last, so it wins over the fixture API.
      await mockApi(page)
      await hold(page, '**/api/topics/linear-equations?**')
      await page.goto('/topics/linear-equations')
      await expect(page.locator('[data-state="loading"]')).toBeVisible()
    },
  ],
  [
    'topic: loaded',
    async (page) => {
      await mockApi(page)
      await page.goto('/topics/linear-equations')
      await expect(page.getByRole('heading', { name: 'The idea', exact: true })).toBeVisible()
    },
  ],
  ...(['Why?', 'Another way', 'Picture'] as const).map(
    (tab): [string, (page: Page) => Promise<void>] => [
      `topic: a step explained, ${tab}`,
      async (page) => {
        await mockApi(page)
        await page.goto('/topics/linear-equations')
        await page.getByRole('button', { name: /3 x equals 15/ }).click()
        const dialog = page.getByRole('dialog')
        // On a phone the explanation opens in a bottom sheet.
        const scope = (await dialog.count()) ? dialog : page.locator('#example')
        await scope.getByRole('tab', { name: tab }).click()
        await expect(scope.getByRole('tab', { name: tab })).toHaveAttribute('aria-selected', 'true')
      },
    ],
  ),
  [
    'topic: the last worked example, a question open',
    async (page) => {
      await mockApi(page)
      await page.goto('/topics/linear-equations')
      await page.getByRole('button', { name: 'Next worked example' }).click()
      await page.getByRole('button', { name: 'Next worked example' }).click()
      await page.getByRole('button', { name: /Can I just move the 5/ }).click()
      await expect(page.getByText(/is a shortcut for subtracting 5/)).toBeVisible()
    },
  ],
  [
    'topic: served in English under an Arabic UI',
    async (page) => {
      await mockApi(page)
      await page.goto('/topics/fractions?lng=ar')
      await expect(page.getByText('معروض بالإنجليزية: لم يُترجم بعد')).toBeVisible()
    },
  ],
  [
    'topic: failed to load',
    async (page) => {
      await mockApi(page)
      await failWith(page, '**/api/topics/fractions?**', 500)
      await page.goto('/topics/fractions')
      await expect(page.getByRole('alert')).toBeVisible({ timeout: 15_000 })
    },
  ],
  [
    'topic: unknown',
    async (page) => {
      await mockApi(page)
      await page.goto('/topics/algebra')
      await expect(page.getByRole('heading', { level: 1 })).toHaveText('Page not found')
    },
  ],
  // Practice
  [
    'practice: a problem',
    async (page) => {
      await mockApi(page)
      await page.goto('/practice/linear-equations/1')
      await expect(page.getByRole('math', { name: '8 x equals 56' })).toBeVisible()
    },
  ],
  [
    'practice: the last problem',
    async (page) => {
      await mockApi(page)
      await page.goto('/practice/fractions/8')
      await expect(page.getByRole('link', { name: 'Next problem' })).toHaveCount(0)
    },
  ],
  [
    'practice: checked with nothing written',
    async (page) => {
      await mockApi(page)
      await page.goto('/practice/linear-equations/1')
      await page.getByRole('button', { name: 'Check my working' }).click()
      await expect(page.getByText('Write or type at least one line first.')).toBeVisible()
    },
  ],
  [
    'practice: every line follows',
    async (page) => {
      await checkWorking(page, 'check/all-follow.json')
      await expect(page.locator('[data-check="all_follow"]')).toBeVisible()
    },
  ],
  [
    'practice: a line that does not follow',
    async (page) => {
      await checkWorking(page, 'check/bad-line.json')
      await expect(page.locator('[data-check="line_doesnt_follow"]')).toBeVisible()
    },
  ],
  [
    'practice: the check failed',
    async (page) => {
      await checkWorking(page, { status: 500 })
      await expect(page.getByRole('alert')).toBeVisible()
    },
  ],
  [
    'practice: one hint open',
    async (page) => {
      await showHints(page, 1)
      await expect(page.getByText(/We want the value of/)).toBeVisible()
    },
  ],
  [
    'practice: the answer shown',
    async (page) => {
      await showHints(page, 4)
      await expect(page.getByRole('link', { name: 'Open the worked example.' })).toBeVisible()
    },
  ],
  [
    'practice start: no topic has practice',
    async (page) => {
      await mockApi(page)
      await page.route('**/api/topics/*?**', async (route) => {
        const pack = await (await route.fetch()).json()
        await route.fulfill({ json: { ...pack, practice: [] } })
      })
      await page.goto('/practice')
      await expect(page.getByText('There are no practice problems yet.')).toBeVisible()
    },
  ],
  // Mistake
  [
    'mistake: empty',
    async (page) => {
      await mockApi(page)
      await page.goto('/mistake')
      await expect(page.getByRole('button', { name: 'Explain this' })).toBeVisible()
    },
  ],
  [
    'mistake: missing problem and answer',
    async (page) => {
      await mockApi(page)
      await page.goto('/mistake')
      await page.getByRole('button', { name: 'Explain this' }).click()
      await expect(page.getByText('Add the problem first.')).toBeVisible()
    },
  ],
  [
    'mistake: write and photo tabs',
    async (page) => {
      await mockApi(page)
      await page.goto('/mistake')
      await page.getByRole('tab', { name: 'Write' }).first().click()
      await page.getByRole('tab', { name: 'Photo' }).nth(1).click()
      await expect(page.getByRole('tab', { name: 'Photo' }).nth(1)).toHaveAttribute(
        'aria-selected',
        'true',
      )
    },
  ],
  ...(['diagnosed', 'correct', 'not-simplified', 'slip', 'unclear', 'out-of-scope'] as const).map(
    (state): [string, (page: Page) => Promise<void>] => [
      `mistake: the ${state} result`,
      async (page) => {
        await explain(page, { mistake: () => ({ body: fixture(`mistake/${state}.json`) }) })
        await expect(page.locator(`[data-status="${state.replaceAll('-', '_')}"]`)).toBeVisible()
      },
    ],
  ),
  [
    'mistake: rate limited',
    async (page) => {
      await explain(page, {
        mistake: () => ({ status: 429, body: {}, headers: { 'Retry-After': '30' } }),
      })
      await expect(page.getByRole('alert')).toContainText('Please wait 30 seconds.')
    },
  ],
  // Elsewhere
  [
    'not found',
    async (page) => {
      await mockApi(page)
      await page.goto('/no-such-page')
      await expect(page.getByRole('heading', { level: 1 })).toHaveText('Page not found')
    },
  ],
]

for (const [name, reach] of STATES) {
  test(name, async ({ page }) => {
    await reach(page)
    await checkState(page, name, { loading: name.endsWith(': loading') })
  })
}

const REASONS = [
  'problem_unreadable',
  'answer_unreadable',
  'unsupported',
  'timeout',
  'ai_unavailable',
  'ai_unclear',
  'ai_out_of_scope',
  'ai_unverified_math',
  'math_error',
]

test('mistake: every abstain reason is shown and fits', async ({ page }) => {
  let reason = REASONS[0]
  const unclear = fixture('mistake/unclear.json') as object
  await explain(page, { mistake: () => ({ body: { ...unclear, reason, diagnosis: null } }) })
  for (const [i, r] of REASONS.entries()) {
    if (i > 0) {
      reason = r
      await page.getByRole('button', { name: 'Try another answer' }).click()
      await typeMath(page, 'What your student answered', '2/5')
      await page.getByRole('button', { name: 'Explain this' }).click()
    }
    await expect(page.locator('[data-reason]')).toHaveAttribute('data-reason', r)
    await expectNoSideScroll(page, r)
    await expectNothingClipped(page, r)
  }
  // The markup is the same for every reason; one axe run covers it.
  await expectNoAxeViolations(page)
})
