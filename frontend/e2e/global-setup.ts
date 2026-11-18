// With BASE_URL, the deployed app may be scaled to zero: wake it before the first test,
// so a ~20 s cold start isn't charged to whichever test runs first.
export default async function globalSetup(): Promise<void> {
  const base = process.env.BASE_URL
  if (!base) return
  const url = new URL('/api/health', base).toString()
  const deadline = Date.now() + 120_000
  for (;;) {
    try {
      const res = await fetch(url, { signal: AbortSignal.timeout(30_000) })
      if (res.ok) return
    } catch {
      // still starting: retry until the deadline
    }
    if (Date.now() > deadline) throw new Error(`${url} did not answer 200 within 2 minutes`)
    await new Promise((r) => setTimeout(r, 2_000))
  }
}
