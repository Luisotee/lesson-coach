import { motion, useReducedMotion } from 'motion/react'
import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'

type ApiState = 'checking' | 'ok' | 'down'

export default function App() {
  const { t } = useTranslation()
  const reduceMotion = useReducedMotion()
  const [api, setApi] = useState<ApiState>('checking')

  useEffect(() => {
    let cancelled = false
    fetch('/api/health')
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(String(r.status)))))
      .then((body: { status?: string }) => {
        if (!cancelled) setApi(body.status === 'ok' ? 'ok' : 'down')
      })
      .catch(() => {
        if (!cancelled) setApi('down')
      })
    return () => {
      cancelled = true
    }
  }, [])

  const apiLabel = { checking: t('app.apiChecking'), ok: t('app.apiOk'), down: t('app.apiDown') }[
    api
  ]

  return (
    <main className="mx-auto flex min-h-svh max-w-2xl flex-col justify-center gap-6 px-6">
      <motion.h1
        className="text-5xl font-bold text-navy"
        initial={reduceMotion ? false : { opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
      >
        {t('app.title')}
      </motion.h1>
      <p className="text-lg">
        <span className="bg-highlight px-1">{t('app.tagline')}</span>
      </p>
      <p className="text-sm lowercase">
        {t('app.apiStatus')}:{' '}
        <span className={api === 'ok' ? 'font-semibold text-green-text' : 'font-semibold'}>
          {apiLabel}
        </span>
      </p>
    </main>
  )
}
