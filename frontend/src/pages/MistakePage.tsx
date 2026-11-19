import { Loader2, ShieldCheck } from 'lucide-react'
import { useEffect, useRef, useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { useApiLang, useMistake, useTopicTitle } from '@/api/queries'
import type { MistakeRequest } from '@/api/types'
import {
  MathInput,
  type ConfirmedExpression,
  type ConfirmedLines,
  type MathInputHandle,
} from '@/components/input'
import { LoadError, Loading } from '@/components/LoadState'
import { MistakeResult } from '@/components/mistake/MistakeResult'
import { usePageTitle } from '@/components/shell/hooks'
import { Button } from '@/components/ui/button'
import { TOPIC_IDS, type TopicId } from '@/content/topics'
import { useRetryWait } from '@/hooks/useRetryWait'
import { smoothly, smoothlyThen } from '@/lib/smooth'
import { cn } from '@/lib/utils'

/** "A student wrote this": the problem, the student's answer and optional working in; the
 * likely reason and what to say out. Nothing is stored; one request per "Explain this". */
export function MistakePage() {
  const { t } = useTranslation()
  usePageTitle(t('mistake.title'))
  const lang = useApiLang()
  const titleOf = useTopicTitle()
  const mistake = useMistake()
  // After a 429, "Explain this" waits out Retry-After like the Retry button does.
  const wait = useRetryWait(mistake.error)

  const [topic, setTopic] = useState<TopicId | undefined>()
  const [problem, setProblem] = useState<ConfirmedExpression | null>(null)
  const [answer, setAnswer] = useState<ConfirmedExpression | null>(null)
  const [working, setWorking] = useState<ConfirmedLines | null>(null)
  const [errors, setErrors] = useState<{ problem?: string; answer?: string; working?: string }>({})
  // Changing the key resets the answer input ("Try another answer").
  const [answerKey, setAnswerKey] = useState(0)
  const focusAnswerNext = useRef(false)
  const problemRef = useRef<MathInputHandle>(null)
  const answerRef = useRef<MathInputHandle>(null)
  const workingRef = useRef<MathInputHandle>(null)
  const answerBox = useRef<HTMLDivElement>(null)
  const lastRequest = useRef<MistakeRequest | null>(null)
  // The topic the shown result was asked with; the chips may have changed since.
  const [sentTopic, setSentTopic] = useState<TopicId | undefined>()

  useEffect(() => {
    if (!focusAnswerNext.current) return
    focusAnswerNext.current = false
    // The fresh input may still be loading its editor; MathInput honours the focus once it can.
    answerRef.current?.focus()
  }, [answerKey])

  // When the result sits below the form (phones, narrow windows), bring it up (smoothly) while it
  // loads, so "Explain this" visibly leads somewhere. Side by side, it is already beside the
  // button.
  const resultRef = useRef<HTMLElement>(null)
  useEffect(() => {
    const result = resultRef.current
    const form = result?.previousElementSibling
    if (!mistake.isPending || !result || !form) return
    if (result.getBoundingClientRect().top >= form.getBoundingClientRect().bottom)
      smoothly(() => result.scrollIntoView({ block: 'start' }))
  }, [mistake.isPending])

  const send = (body: MistakeRequest) => {
    lastRequest.current = body
    setSentTopic(body.topic)
    mistake.mutate(body)
  }

  const onSubmit = (e: FormEvent) => {
    e.preventDefault()
    // Lines read from a drawing or photo but not used yet: say so, not "nothing entered".
    const unused = (ref: typeof problemRef, action: string) =>
      ref.current?.isUnconfirmed() ? t('input.useFirst', { action }) : undefined
    const next = {
      problem: problem
        ? undefined
        : (unused(problemRef, t('mistake.useProblem')) ?? t('mistake.needProblem')),
      answer: answer
        ? undefined
        : (unused(answerRef, t('mistake.useAnswer')) ?? t('mistake.needAnswer')),
      // The working is optional, but read lines left unused would be silently dropped.
      working: working ? undefined : unused(workingRef, t('mistake.useWorking')),
    }
    setErrors(next)
    if (next.problem) return problemRef.current?.focus()
    if (next.answer) return answerRef.current?.focus()
    if (next.working) return workingRef.current?.focus()
    if (!problem || !answer) return
    send({
      problem: problem.math,
      answer: answer.math,
      working: working?.lines ?? [],
      ...(topic && { topic }),
      lang,
    })
  }

  // A result describes what was sent: once the inputs change, it no longer applies.
  const clearResult = () => {
    if (!mistake.isIdle) mistake.reset()
  }

  const tryAnother = () => {
    // Blur first: MathLive drops a focus request while the focused element changes.
    ;(document.activeElement as HTMLElement | null)?.blur()
    const again = () => {
      mistake.reset()
      setAnswer(null)
      setAnswerKey((k) => k + 1)
      focusAnswerNext.current = true
    }
    // On a phone the answer field is a screen or more above: glide up to it first, then clear
    // the result (clearing first would shorten the page under the reader, a jump).
    // Above the view, or under the sticky header (--header-h, 0 when it scrolls away).
    const field = answerBox.current
    const header =
      parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--header-h')) || 0
    if (field && field.getBoundingClientRect().top < header)
      smoothlyThen(() => field.scrollIntoView({ block: 'center' }), again)
    else again()
  }

  return (
    // Until there is a result, the form is the page: one centred column, not half an empty page.
    <div
      className={cn(
        'mx-auto flex flex-col gap-8 px-4 py-10 sm:px-6',
        mistake.isIdle ? 'max-w-3xl' : 'max-w-[1200px]',
      )}
    >
      <div className="flex max-w-2xl flex-col gap-3">
        <h1 className="text-[clamp(32px,4vw,48px)] leading-tight font-bold tracking-tight">
          {t('mistake.title')}
        </h1>
        <p className="text-lg leading-relaxed text-muted-foreground">{t('mistake.intro')}</p>
      </div>

      <div className="flex flex-wrap items-start gap-8">
        <form
          noValidate
          onSubmit={onSubmit}
          className="flex min-w-0 flex-[1_1_380px] flex-col gap-6 rounded-[20px] border border-line bg-white p-5 sm:p-6"
        >
          <fieldset className="flex flex-col gap-2">
            <legend className="mb-2 text-sm font-semibold text-muted-foreground lowercase">
              {t('mistake.topicLegend')}
            </legend>
            <div className="flex flex-wrap gap-2">
              {TOPIC_IDS.map((id) => (
                <button
                  key={id}
                  type="button"
                  aria-pressed={topic === id}
                  onClick={() => setTopic(topic === id ? undefined : id)}
                  className={cn(
                    'min-h-11 rounded-full border px-4 text-sm font-medium',
                    topic === id
                      ? 'border-navy bg-paleblue text-navy'
                      : 'border-line bg-white text-[#3a4458] hover:border-line-strong hover:bg-[#eef1f4]',
                  )}
                >
                  {titleOf(id)}
                </button>
              ))}
            </div>
          </fieldset>

          <MathInput
            ref={problemRef}
            shape="expression"
            label={t('mistake.problemLabel')}
            confirmLabel={t('mistake.useProblem')}
            description={t('mistake.problemHint')}
            error={errors.problem}
            onChange={(v) => {
              clearResult()
              setProblem(v)
              if (v) setErrors((e) => ({ ...e, problem: undefined }))
            }}
          />
          <div ref={answerBox}>
            <MathInput
              key={answerKey}
              ref={answerRef}
              shape="expression"
              label={t('mistake.answerLabel')}
              confirmLabel={t('mistake.useAnswer')}
              error={errors.answer}
              onChange={(v) => {
                clearResult()
                setAnswer(v)
                if (v) setErrors((e) => ({ ...e, answer: undefined }))
              }}
            />
          </div>
          <MathInput
            ref={workingRef}
            shape="lines"
            label={t('mistake.workingLabel')}
            confirmLabel={t('mistake.useWorking')}
            error={errors.working}
            onChange={(v) => {
              clearResult()
              setWorking(v)
              if (v) setErrors((e) => ({ ...e, working: undefined }))
            }}
          />

          <p className="flex items-start gap-2 text-sm text-muted-foreground">
            <ShieldCheck aria-hidden="true" className="mt-0.5 size-4 flex-none text-green" />
            {t('mistake.privacy')}
          </p>
          <Button
            type="submit"
            className="min-h-12 self-start px-6 text-base"
            disabled={mistake.isPending || wait > 0}
          >
            {mistake.isPending && (
              <Loader2 aria-hidden="true" className="animate-spin motion-reduce:animate-none" />
            )}
            {mistake.isPending ? t('mistake.explaining') : t('mistake.explain')}
          </Button>
        </form>

        <section
          ref={resultRef}
          aria-live="polite"
          aria-label={t('mistake.resultHeading')}
          // Kept mounted while idle (visually hidden), so the live region announces the result.
          className={cn(
            'flex min-w-0 flex-[1.2_1_420px] flex-col gap-4',
            mistake.isIdle && 'sr-only',
          )}
        >
          {mistake.isPending && <Loading lines={4} />}
          {mistake.isError && (
            <LoadError
              error={mistake.error}
              onRetry={() => lastRequest.current && send(lastRequest.current)}
            />
          )}
          {mistake.data && (
            <MistakeResult result={mistake.data} topic={sentTopic} onTryAnother={tryAnother} />
          )}
        </section>
      </div>
    </div>
  )
}
