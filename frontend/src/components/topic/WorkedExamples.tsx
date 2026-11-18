import { ChevronLeft, ChevronRight, Check, Sparkles } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import type { WorkedExample } from '@/api/types'
import { CheckLine, EquationLine, MathExpr, Notebook } from '@/components/math'
import { ExplanationPanel, type ExplanationMode } from '@/components/topic/ExplanationPanel'
import { Button } from '@/components/ui/button'
import {
  Drawer,
  DrawerContent,
  DrawerDescription,
  DrawerFooter,
  DrawerHeader,
  DrawerTitle,
} from '@/components/ui/drawer'
import { PHONE_QUERY, useMediaQuery } from '@/hooks/useMediaQuery'
import { isContinued, parseOp } from '@/math/parse'
import { speakOp } from '@/math/speech'

/** "Step 2 · subtract 5 from both sides": the operation that produced this line. */
function useStepHeading(example: WorkedExample, index: number): string {
  const { t } = useTranslation()
  const prev = index > 0 ? parseOp(example.steps[index - 1].op) : null
  if (index === 0) return t('topic.stepStart', { n: 1 })
  if (prev?.ok) return t('topic.stepWithOp', { n: index + 1, op: speakOp(prev.value, t) })
  return t('topic.step', { n: index + 1 })
}

function lineText(step: { left: string; right: string }): string {
  return step.right ? `${step.left} = ${step.right}` : step.left
}

/**
 * The worked examples: one notebook at a time with Previous/Next example. Tapping a line
 * shows why it works in three ways, beside the notebook on wider screens and in a bottom
 * sheet on phones, where Previous/Next step move through the lines.
 */
export function WorkedExamples({ examples }: { examples: WorkedExample[] }) {
  const { t } = useTranslation()
  const phone = useMediaQuery(PHONE_QUERY)
  const [exampleIndex, setExampleIndex] = useState(0)
  const [stepIndex, setStepIndex] = useState(0)
  const [mode, setMode] = useState<ExplanationMode>('why')
  const [sheetOpen, setSheetOpen] = useState(false)

  const example = examples[exampleIndex]
  const step = example.steps[stepIndex]
  const heading = useStepHeading(example, stepIndex)
  const aiWritten = (example.ai_generated?.length ?? 0) > 0

  const goToExample = (i: number) => {
    setExampleIndex(i)
    setStepIndex(0)
  }
  const select = (i: number) => {
    setStepIndex(i)
    if (phone) setSheetOpen(true)
  }

  const panel = (
    <ExplanationPanel step={step} heading={heading} mode={mode} onModeChange={setMode} />
  )

  return (
    <section
      id="example"
      aria-labelledby="example-heading"
      className="scroll-mt-24 rounded-3xl border border-line bg-white p-2 shadow-[0_30px_60px_-40px_rgba(23,43,83,.35)] print:hidden"
    >
      <div className="flex flex-wrap items-center justify-between gap-3 px-4 pt-4 pb-2">
        <div className="flex flex-col gap-1">
          <div className="flex items-center gap-1">
            <Button
              variant="ghost"
              size="icon"
              className="size-11"
              disabled={exampleIndex === 0}
              onClick={() => goToExample(exampleIndex - 1)}
              aria-label={t('topic.previousExample')}
            >
              <ChevronLeft aria-hidden="true" className="rtl:-scale-x-100" />
            </Button>
            <span
              className="text-xs font-semibold text-muted-foreground lowercase"
              aria-live="polite"
            >
              {t('topic.exampleOf', { n: exampleIndex + 1, total: examples.length })}
            </span>
            <Button
              variant="ghost"
              size="icon"
              className="size-11"
              disabled={exampleIndex === examples.length - 1}
              onClick={() => goToExample(exampleIndex + 1)}
              aria-label={t('topic.nextExample')}
            >
              <ChevronRight aria-hidden="true" className="rtl:-scale-x-100" />
            </Button>
          </div>
          <h2 id="example-heading" className="text-2xl font-semibold">
            {example.prompt ?? t(`topic.kind.${example.problem.kind}`)}{' '}
            <MathExpr expr={example.problem.expr} className="font-normal" />
          </h2>
        </div>
        <span className="inline-flex items-center gap-2 rounded-full bg-[#ecfdf5] px-3 py-1.5 text-[13px] font-semibold text-green-text">
          <Check aria-hidden="true" className="size-3.5" />
          {t('topic.checkedBadge')}
        </span>
      </div>

      <div className="flex flex-wrap gap-2 p-2">
        <div className="min-w-0 flex-[1_1_300px]">
          <p className="mb-1 ps-10 text-xs text-muted-foreground">{t('topic.tapLine')}</p>
          <Notebook
            label={t('topic.exampleLabel', { n: exampleIndex + 1 })}
            numbered
            key={exampleIndex}
          >
            {example.steps.map((s, i) => (
              <EquationLine
                key={i}
                index={i}
                left={s.left}
                right={s.right}
                op={s.op}
                continued={isContinued(example.steps, i)}
                selected={i === stepIndex}
                onSelect={() => select(i)}
              />
            ))}
          </Notebook>
          {example.problem.kind === 'solve' && (
            <CheckLine equation={example.problem.expr} answer={example.answer} />
          )}
        </div>

        {!phone && (
          <div className="flex min-w-0 flex-[1.3_1_340px] flex-col overflow-hidden rounded-[18px] border border-line bg-ground">
            {panel}
            <p className="mt-auto flex items-center gap-2 border-t border-line px-6 py-3 text-xs text-muted-foreground">
              <Sparkles aria-hidden="true" className="size-3.5" />
              {aiWritten ? t('topic.aiLabel') : t('topic.checkedLabel')}
            </p>
          </div>
        )}
      </div>

      {phone && (
        <Drawer open={sheetOpen} onOpenChange={setSheetOpen}>
          <DrawerContent>
            <DrawerHeader className="text-start">
              <DrawerTitle>{heading}</DrawerTitle>
              <DrawerDescription asChild>
                <div>
                  <MathExpr expr={lineText(step)} className="text-2xl text-navy" />
                </div>
              </DrawerDescription>
            </DrawerHeader>
            <div className="overflow-y-auto">{panel}</div>
            <DrawerFooter className="flex-row justify-between">
              <Button
                variant="outline"
                className="min-h-11"
                disabled={stepIndex === 0}
                onClick={() => setStepIndex(stepIndex - 1)}
              >
                {t('topic.previousStep')}
              </Button>
              <Button
                className="min-h-11"
                disabled={stepIndex === example.steps.length - 1}
                onClick={() => setStepIndex(stepIndex + 1)}
              >
                {t('topic.nextStep')}
              </Button>
            </DrawerFooter>
          </DrawerContent>
        </Drawer>
      )}
      {phone && (
        <p className="flex items-center gap-2 px-4 pb-3 text-xs text-muted-foreground">
          <Sparkles aria-hidden="true" className="size-3.5" />
          {aiWritten ? t('topic.aiLabel') : t('topic.checkedLabel')}
        </p>
      )}
    </section>
  )
}
