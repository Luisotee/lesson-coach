import { useState, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { MathInput, type ConfirmedExpression, type ConfirmedLines } from '@/components/input'
import { PageFrame } from '@/pages/PageFrame'

function Card({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="flex min-w-0 flex-col gap-4 rounded-2xl border border-line bg-white p-5">
      <h2 className="text-xl font-semibold">{title}</h2>
      {children}
    </section>
  )
}

/** The value as the page gets it: JSON, the shape sent to the API. */
function Received({ value }: { value: ConfirmedExpression | ConfirmedLines | null }) {
  const { t } = useTranslation()
  return (
    <div className="flex flex-col gap-1">
      <h3 className="text-sm font-semibold">{t('demo.inputReceived')}</h3>
      <output
        dir="ltr"
        data-testid="received"
        className="block overflow-x-auto rounded-lg bg-ground p-3 font-mono text-sm whitespace-pre-wrap"
      >
        {value ? JSON.stringify(value) : t('demo.inputNothing')}
      </output>
    </div>
  )
}

/** Both shapes of MathInput, with what each hands to its page. */
export function InputDemoPage() {
  const { t } = useTranslation()
  const [expression, setExpression] = useState<ConfirmedExpression | null>(null)
  const [lines, setLines] = useState<ConfirmedLines | null>(null)
  return (
    <PageFrame title={t('demo.inputTitle')}>
      <p className="max-w-3xl text-lg text-muted-foreground">{t('demo.inputIntro')}</p>
      <Card title={t('demo.inputExpression')}>
        <MathInput
          shape="expression"
          label={t('demo.inputExpressionLabel')}
          description={t('demo.inputExpressionHint')}
          onChange={setExpression}
        />
        <Received value={expression} />
      </Card>
      <Card title={t('demo.inputLines')}>
        <MathInput
          shape="lines"
          label={t('demo.inputLinesLabel')}
          defaultMode="write"
          onChange={setLines}
        />
        <Received value={lines} />
      </Card>
    </PageFrame>
  )
}
