import { ScanText } from 'lucide-react'
import { useReducer } from 'react'
import { useTranslation } from 'react-i18next'
import { DrawingBoard } from '@/components/input/DrawingBoard'
import { exportDrawing } from '@/components/input/exportDrawing'
import { ReadingStatus, TypeInstead } from '@/components/input/Reading'
import { emptyHistory, historyReducer, visibleStrokes } from '@/components/input/strokes'
import { TranscriptionReview } from '@/components/input/TranscriptionReview'
import type { ReviewLine } from '@/components/input/types'
import { useTranscription } from '@/components/input/useTranscription'
import { Button } from '@/components/ui/button'

/**
 * Write on squared paper, have it read, confirm the lines. The board is locked while it is
 * being read, so the lines shown for confirmation are always of the drawing that was sent.
 */
export function WritePanel({
  label,
  single,
  onLines,
  onTypeInstead,
}: {
  label: string
  single: boolean
  /** The confirmed lines, or null when nothing is confirmed. */
  onLines: (lines: ReviewLine[] | null) => void
  onTypeInstead: () => void
}) {
  const { t } = useTranslation()
  const [history, dispatch] = useReducer(historyReducer, emptyHistory)
  const { phase, run, reset } = useTranscription()
  const strokes = visibleStrokes(history)
  const reading = phase.kind === 'reading'

  if (phase.kind === 'review') {
    return (
      <div className="flex flex-col gap-3">
        <TranscriptionReview
          initial={phase.lines}
          single={single}
          retakeLabel={t('input.write.again')}
          onConfirm={onLines}
          onUnconfirm={() => onLines(null)}
          onRetake={() => {
            onLines(null)
            reset()
          }}
        />
        <div>
          <TypeInstead onClick={onTypeInstead} />
        </div>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-3">
      <p className="text-muted-foreground">
        {t(single ? 'input.write.introOne' : 'input.write.introLines')}
      </p>
      <DrawingBoard
        label={t('input.write.board', { label })}
        history={history}
        dispatch={(e) => {
          dispatch(e)
          if (phase.kind === 'failed') reset()
        }}
        rows={single ? 4 : 8}
        locked={reading}
      />
      <div className="flex flex-wrap items-center gap-2">
        <Button
          data-main-control
          type="button"
          className="min-h-11 px-5 aria-disabled:opacity-50"
          aria-disabled={strokes.length === 0 || reading || undefined}
          onClick={() => {
            if (strokes.length === 0 || reading) return
            void run(() => exportDrawing(strokes))
          }}
        >
          <ScanText aria-hidden="true" />
          {t('input.write.read')}
        </Button>
        <TypeInstead onClick={onTypeInstead} />
      </div>
      <ReadingStatus phase={phase} readingLabel={t('input.write.reading')} />
    </div>
  )
}
