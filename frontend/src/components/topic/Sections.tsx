import { ArrowRight, ExternalLink } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router'
import { useTopicTitle } from '@/api/queries'
import type { AkeliusLesson, Misconception, Pack } from '@/api/types'
import { MathExpr, Pen } from '@/components/math'
import { RichText } from '@/components/RichText'
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from '@/components/ui/accordion'

/** Prose that verification dropped is said to be unavailable, never filled in. */
function Prose({ text }: { text: string | null }) {
  const { t } = useTranslation()
  return text ? (
    <RichText as="p" text={text} className="text-base leading-[1.65]" />
  ) : (
    <p className="text-muted-foreground">{t('topic.textUnavailable')}</p>
  )
}

export function IdeaCards({ pack }: { pack: Pack }) {
  const { t } = useTranslation()
  return (
    <section
      id="idea"
      aria-label={t('topic.sections.idea')}
      className="grid scroll-mt-24 grid-cols-[repeat(auto-fit,minmax(min(260px,100%),1fr))] gap-4 print:hidden"
    >
      <div className="rounded-[20px] border border-line bg-white p-6 text-[#3a4458]">
        <h2 className="mb-2.5 text-xl font-semibold text-navy">{t('topic.idea')}</h2>
        <Prose text={pack.idea} />
      </div>
      <div className="rounded-[20px] bg-navy p-6 text-ground">
        <h2 className="mb-2.5 text-xl font-semibold text-highlight">{t('topic.whyItWorks')}</h2>
        <Prose text={pack.why_it_works} />
      </div>
    </section>
  )
}

export function RefreshFirst({ ids }: { ids: string[] }) {
  const { t } = useTranslation()
  const titleOf = useTopicTitle()
  return (
    <section
      id="refresh"
      aria-labelledby="refresh-heading"
      className="flex scroll-mt-24 flex-wrap items-center gap-2.5 print:hidden"
    >
      <h2 id="refresh-heading" className="me-1 text-[15px] font-semibold text-muted-foreground">
        {t('topic.refreshFirst')}
      </h2>
      <ul className="flex flex-wrap gap-2.5">
        {ids.map((id) => (
          <li key={id}>
            <Link
              to={`/topics/${id}`}
              className="inline-flex min-h-11 items-center rounded-full border border-line bg-white px-3.5 text-sm font-medium text-navy no-underline hover:border-line-strong hover:bg-[#eef1f4]"
            >
              {titleOf(id)}
            </Link>
          </li>
        ))}
      </ul>
    </section>
  )
}

function MisconceptionCard({ m }: { m: Misconception }) {
  const { t } = useTranslation()
  return (
    <article className="flex flex-col gap-3 rounded-[20px] border border-line bg-white p-5">
      <h3 className="text-lg leading-snug font-semibold">
        <RichText text={m.belief} />
      </h3>
      <div
        className="paper flex flex-wrap items-center gap-2 rounded-xl border border-line px-3 py-2 text-xl"
        dir="ltr"
      >
        <Pen variant="pencil">
          <MathExpr expr={m.example_problem.expr} />
        </Pen>
        <span aria-hidden="true">→</span>
        <span className="sr-only">{t('topic.studentWrites')}</span>
        <Pen variant="pencil">
          <MathExpr expr={m.example_wrong_answer} />
        </Pen>
      </div>
      <p className="text-[15px] leading-relaxed text-[#3a4458]">
        <b>{t('topic.whyItFeelsRight')}</b> <RichText text={m.why_it_feels_right} />
      </p>
      <p className="mt-auto rounded-xl bg-paleblue/40 px-3 py-2 text-[15px]">
        <b>{t('topic.ask')}</b> <RichText text={m.what_to_say.probe} />
      </p>
    </article>
  )
}

export function Misconceptions({ items }: { items: Misconception[] }) {
  const { t } = useTranslation()
  return (
    <section id="mistakes" aria-labelledby="mistakes-heading" className="scroll-mt-24 print:hidden">
      <h2 id="mistakes-heading" className="mb-4 text-2xl font-semibold">
        {t('topic.mistakesHeading')}
      </h2>
      <div className="grid grid-cols-[repeat(auto-fit,minmax(min(280px,100%),1fr))] gap-4">
        {items.map((m) => (
          <MisconceptionCard key={m.id} m={m} />
        ))}
      </div>
    </section>
  )
}

export function StudentQuestions({ items }: { items: Pack['questions'] }) {
  const { t } = useTranslation()
  return (
    <section
      id="questions"
      aria-labelledby="questions-heading"
      className="scroll-mt-24 print:hidden"
    >
      <h2 id="questions-heading" className="mb-4 text-2xl font-semibold">
        {t('topic.questionsHeading')}
      </h2>
      <Accordion
        type="single"
        collapsible
        defaultValue="q0"
        className="rounded-[20px] border border-line bg-white px-5"
      >
        {items.map((q, i) => (
          <AccordionItem key={i} value={`q${i}`}>
            <AccordionTrigger className="min-h-11 text-base font-semibold hover:no-underline">
              <span>
                “<RichText text={q.question} />”
              </span>
            </AccordionTrigger>
            <AccordionContent className="text-[15px] leading-relaxed text-[#3a4458]">
              <RichText as="p" text={q.answer} />
            </AccordionContent>
          </AccordionItem>
        ))}
      </Accordion>
    </section>
  )
}

function AkeliusLinks({ lessons }: { lessons: AkeliusLesson[] }) {
  const { t } = useTranslation()
  return (
    <div className="flex flex-col gap-2 rounded-[20px] border border-line bg-white p-5 print:hidden">
      <h3 className="font-semibold">{t('topic.akeliusHeading')}</h3>
      <ul className="flex flex-col gap-1">
        {lessons.map((l) => (
          <li key={l.url}>
            <a
              href={l.url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex min-h-11 items-center gap-2 font-semibold text-link-ink underline underline-offset-2"
            >
              {t('topic.akeliusLesson', { title: l.title, grade: l.grade })}
              <ExternalLink aria-hidden="true" className="size-4" />
              <span className="sr-only">{t('common.newTab')}</span>
            </a>
          </li>
        ))}
      </ul>
    </div>
  )
}

/** The outline as a timeline. It is the part of the page that prints. */
export function LessonOutline({ pack }: { pack: Pack }) {
  const { t } = useTranslation()
  // Running start and end minutes, for the "0–5 min" labels.
  const rows = pack.outline.reduce<(Pack['outline'][number] & { from: number; to: number })[]>(
    (acc, o) => {
      const from = acc.length ? acc[acc.length - 1].to : 0
      return [...acc, { ...o, from, to: from + o.minutes }]
    },
    [],
  )
  const total = rows.length ? rows[rows.length - 1].to : 0
  return (
    <section
      id="outline"
      aria-labelledby="outline-heading"
      className="flex scroll-mt-24 flex-col gap-4"
      data-print
    >
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 id="outline-heading" className="text-2xl font-semibold">
          {t('topic.outlineHeading')}
        </h2>
        <span className="text-sm text-muted-foreground">
          {t('topic.outlineTotal', { minutes: total })}
        </span>
      </div>
      <ol className="flex flex-col rounded-[20px] border border-line bg-white p-5 print:border-0 print:p-0">
        {rows.map((o, i) => (
          <li key={i} className="flex gap-4 pb-5 last:pb-0 print:break-inside-avoid">
            <span aria-hidden="true" className="flex flex-col items-center">
              <span className="mt-1.5 size-3 rounded-full bg-navy" />
              {i < rows.length - 1 && <span className="mt-1 w-0.5 flex-1 bg-line" />}
            </span>
            <span className="flex flex-col gap-1">
              <span className="text-[13px] font-semibold text-link-ink">
                {t('topic.outlineTime', { from: o.from, to: o.to })}
              </span>
              <b>
                <RichText text={o.title} />
              </b>
              <RichText text={o.activity} className="text-[15px] leading-relaxed text-[#3a4458]" />
            </span>
          </li>
        ))}
      </ol>
      {pack.akelius_lessons.length > 0 && <AkeliusLinks lessons={pack.akelius_lessons} />}
      {pack.practice.length > 0 && (
        <Link
          to={`/practice/${pack.topic}/1`}
          className="inline-flex min-h-11 items-center gap-2 self-start font-semibold text-link-ink underline underline-offset-2 print:hidden"
        >
          {t('topic.tryYourself')}
          <ArrowRight aria-hidden="true" className="size-4 rtl:-scale-x-100" />
        </Link>
      )}
    </section>
  )
}
