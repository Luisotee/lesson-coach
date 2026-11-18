import { useEffect, useState } from 'react'
import { ApiError } from '@/api/client'

/**
 * Seconds left before a rate-limited request may be sent again: counts down from the 429's
 * Retry-After, restarts on a new error, and is 0 for any other error or none.
 */
export function useRetryWait(error: unknown): number {
  const wait = error instanceof ApiError && error.status === 429 ? (error.retryAfter ?? 0) : 0
  const [counted, setCounted] = useState(error)
  const [left, setLeft] = useState(wait)
  if (counted !== error) {
    setCounted(error)
    setLeft(wait)
  }
  useEffect(() => {
    if (left <= 0) return
    const id = window.setTimeout(() => setLeft((s) => s - 1), 1000)
    return () => window.clearTimeout(id)
  }, [left])
  return left
}
