/** A failed API call. `retryAfter` is in seconds, from a 429's `Retry-After`. */
export class ApiError extends Error {
  readonly status: number
  readonly retryAfter: number | null
  constructor(status: number, retryAfter: number | null = null) {
    super(`API error ${status}`)
    this.status = status
    this.retryAfter = retryAfter
  }
}

async function handle<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const retry = Number(res.headers.get('Retry-After'))
    throw new ApiError(res.status, Number.isFinite(retry) && retry > 0 ? retry : null)
  }
  return (await res.json()) as T
}

export async function getJson<T>(url: string, signal?: AbortSignal): Promise<T> {
  return handle<T>(await fetch(url, { signal, headers: { Accept: 'application/json' } }))
}

export async function postJson<T>(url: string, body: unknown): Promise<T> {
  return handle<T>(
    await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
      body: JSON.stringify(body),
    }),
  )
}
