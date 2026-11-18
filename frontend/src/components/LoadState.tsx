import { RotateCcw } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { ApiError } from '@/api/client'
import { Button } from '@/components/ui/button'
import { useRetryWait } from '@/hooks/useRetryWait'

/** Placeholder blocks while content loads; announced once to screen readers. */
export function Loading({ lines = 3 }: { lines?: number }) {
  const { t } = useTranslation()
  return (
    <div role="status" className="flex flex-col gap-3" data-state="loading">
      <span className="sr-only">{t('common.loading')}</span>
      {Array.from({ length: lines }, (_, i) => (
        <div
          key={i}
          aria-hidden="true"
          className="h-6 animate-pulse rounded-lg bg-line motion-reduce:animate-none"
          style={{ width: `${90 - i * 15}%` }}
        />
      ))}
    </div>
  )
}

/** A failed load or request, with a retry. Says when the rate limit asks to wait. */
export function LoadError({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const { t } = useTranslation()
  const wait = error instanceof ApiError && error.status === 429 ? error.retryAfter : null
  // Retry stays off until the rate limit's wait is over.
  const left = useRetryWait(error)
  return (
    <div
      role="alert"
      className="flex flex-col items-start gap-3 rounded-2xl border border-line bg-white p-5"
    >
      <p className="font-semibold">{t('common.loadError')}</p>
      {error instanceof ApiError && error.status === 429 && (
        <p className="text-muted-foreground">
          {wait ? t('common.rateLimitedFor', { seconds: wait }) : t('common.rateLimited')}
        </p>
      )}
      {onRetry && (
        <Button variant="outline" className="min-h-11" onClick={onRetry} disabled={left > 0}>
          <RotateCcw aria-hidden="true" />
          {left > 0 ? t('common.retryIn', { seconds: left }) : t('common.retry')}
        </Button>
      )}
    </div>
  )
}
