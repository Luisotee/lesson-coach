import { useTranslation } from 'react-i18next'
import type { ExplainedStep } from '@/api/types'
import { RichText } from '@/components/RichText'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { StepPicture } from '@/components/visual/StepPicture'

import { MODES, type ExplanationMode } from '@/components/topic/modes'

/** The three pre-generated explanations of one step, as tabs. */
export function ExplanationPanel({
  step,
  heading,
  mode,
  onModeChange,
  showHeading = true,
}: {
  step: ExplainedStep
  /** "Step 2 · subtract 5 from both sides" */
  heading: string
  mode: ExplanationMode
  onModeChange: (mode: ExplanationMode) => void
  /** Off where a surrounding title already names the step (the phone sheet). */
  showHeading?: boolean
}) {
  const { t } = useTranslation()
  const e = step.explanations
  return (
    <Tabs value={mode} onValueChange={(v) => onModeChange(v as ExplanationMode)} className="gap-0">
      <TabsList
        aria-label={t('topic.explanationStyle')}
        className="m-3 flex h-auto w-auto gap-1 rounded-[14px] bg-[#eaeef2] p-1.5"
      >
        {MODES.map((m) => (
          <TabsTrigger
            key={m}
            value={m}
            className="min-h-10 rounded-[10px] text-sm font-semibold text-muted-foreground data-[state=active]:bg-white data-[state=active]:text-navy"
          >
            {t(`topic.modes.${m}`)}
          </TabsTrigger>
        ))}
      </TabsList>
      {MODES.map((m) => (
        <TabsContent key={m} value={m} className="min-h-[200px] px-6 pt-1 pb-6">
          {showHeading && <p className="mb-2 text-sm font-semibold text-link-ink">{heading}</p>}
          {!e ? (
            <p className="text-muted-foreground">{t('topic.explanationUnavailable')}</p>
          ) : m === 'visual' ? (
            <StepPicture step={step} caption={e.visual} />
          ) : (
            <RichText
              as="p"
              text={m === 'why' ? e.why : e.another_way}
              className="text-[17px] leading-relaxed"
            />
          )}
        </TabsContent>
      ))}
    </Tabs>
  )
}
