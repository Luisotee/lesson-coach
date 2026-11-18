import { RotateCcw } from 'lucide-react'
import { useState, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import { MathExpr, Pen, StepsNotebook, type PenVariant } from '@/components/math'
import { usePageTitle } from '@/components/shell/hooks'
import { isContinued } from '@/math/parse'
import { speakLine, speakText } from '@/math/speech'
import type { Step } from '@/math/types'
import { PageFrame } from '@/pages/PageFrame'

const EXPRESSIONS = [
  '1/2 + 1/3',
  '(1 + 1)/(2 + 3)',
  '5 - (-3)',
  '(-2)*(-3)',
  '-5 + 3',
  '3*2/5',
  '2*(x + 3)',
  'x**2 + 2*x',
]

const EQUATION: Step[] = [
  { left: '3*x + 5', right: '20', op: '-5' },
  { left: '3*x', right: '15', op: '/3' },
  { left: 'x', right: '5', op: '' },
]

const EXPRESSION_STEPS: Step[] = [
  { left: '-5 - (-3)', right: '', op: '' },
  { left: '-5 + 3', right: '', op: '' },
  { left: '-2', right: '', op: '' },
]

const FRACTION_STEPS: Step[] = [
  { left: '1/2 + 1/3', right: '', op: '' },
  { left: '3/6 + 2/6', right: '', op: '' },
  { left: '5/6', right: '', op: '' },
]

const PENS: PenVariant[] = ['pencil', 'ink', 'green']

function Spoken({ text }: { text: string }) {
  const { t } = useTranslation()
  return <p className="text-sm text-muted-foreground">{t('demo.spoken', { text })}</p>
}

function Card({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="flex flex-col gap-4 rounded-2xl border border-line bg-white p-5">
      <h2 className="text-xl font-semibold">{title}</h2>
      {children}
    </section>
  )
}

function spokenSteps(steps: Step[], t: ReturnType<typeof useTranslation>['t']): string {
  return steps.map((s, i) => speakLine({ ...s, continued: isContinued(steps, i) }, t)).join(' / ')
}

/** Every math component in one place, in the page's direction and inside RTL text. */
export function MathDemoPage() {
  const { t } = useTranslation()
  usePageTitle(t('demo.title'))
  // Remounting the notebook replays its write-on animation.
  const [run, setRun] = useState(0)

  return (
    <PageFrame title={t('demo.title')}>
      <p className="max-w-3xl text-lg text-muted-foreground">{t('demo.intro')}</p>

      <div className="grid grid-cols-[repeat(auto-fit,minmax(min(340px,100%),1fr))] gap-5">
        <Card title={t('demo.fractionHeading')}>
          <MathExpr expr="3/4" className="text-4xl text-ink" />
          <Spoken text={speakText('3/4', t)} />
        </Card>

        <Card title={t('demo.pensHeading')}>
          <ul className="flex flex-col gap-3">
            {PENS.map((pen) => (
              <li key={pen} className="flex flex-wrap items-center gap-4">
                <Pen variant={pen} className="text-3xl">
                  <MathExpr expr="1/2 + 1/3" />
                </Pen>
                <span className="text-sm">{t(`demo.${pen}`)}</span>
              </li>
            ))}
          </ul>
        </Card>
      </div>

      <Card title={t('demo.expressionsHeading')}>
        <ul className="grid grid-cols-[repeat(auto-fit,minmax(min(260px,100%),1fr))] gap-4">
          {EXPRESSIONS.map((expr) => (
            <li key={expr} className="paper flex flex-col gap-2 rounded-xl border border-line p-4">
              <MathExpr expr={expr} className="text-3xl text-ink" />
              <Spoken text={speakText(expr, t)} />
            </li>
          ))}
        </ul>
      </Card>

      <Card title={t('demo.equationHeading')}>
        <div className="flex flex-wrap items-start gap-4">
          <StepsNotebook
            key={run}
            steps={EQUATION}
            label={t('demo.equationLabel')}
            writeOn
            className="min-w-0 flex-1"
          />
          <Button variant="outline" className="min-h-11" onClick={() => setRun((r) => r + 1)}>
            <RotateCcw aria-hidden="true" />
            {t('demo.replay')}
          </Button>
        </div>
        <Spoken text={spokenSteps(EQUATION, t)} />
      </Card>

      <div className="grid grid-cols-[repeat(auto-fit,minmax(min(340px,100%),1fr))] gap-5">
        <Card title={t('demo.expressionHeading')}>
          <StepsNotebook steps={EXPRESSION_STEPS} label={t('demo.expressionLabel')} pen="pencil" />
          <Spoken text={spokenSteps(EXPRESSION_STEPS, t)} />
        </Card>
        <Card title={t('demo.fractionStepsHeading')}>
          <StepsNotebook steps={FRACTION_STEPS} label={t('demo.fractionStepsLabel')} pen="green" />
          <Spoken text={spokenSteps(FRACTION_STEPS, t)} />
        </Card>
      </div>

      <div dir="rtl" data-testid="rtl-panel">
        <Card title={t('demo.rtlHeading')}>
          <p>
            {t('demo.rtlNote')} <MathExpr expr="2*x + 6 = 10" className="text-2xl text-ink" />
          </p>
          <StepsNotebook steps={EQUATION} label={t('demo.equationLabel')} />
        </Card>
      </div>
    </PageFrame>
  )
}
