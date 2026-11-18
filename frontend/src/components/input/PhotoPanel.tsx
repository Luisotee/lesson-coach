import { Camera, ImageUp } from 'lucide-react'
import { useEffect, useRef, useState, type ChangeEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { CropStep } from '@/components/input/CropStep'
import type { Rect } from '@/components/input/crop'
import { cropAndDownscale, loadImage, rotateQuarter } from '@/components/input/image'
import { ReadingStatus, TypeInstead } from '@/components/input/Reading'
import { TranscriptionReview } from '@/components/input/TranscriptionReview'
import type { ReviewLine } from '@/components/input/types'
import { useTranscription, type Phase } from '@/components/input/useTranscription'
import { Button } from '@/components/ui/button'

const ACCEPT = 'image/png,image/jpeg,image/webp'

/**
 * Take or upload a photo, crop it, have it read, confirm the lines. The photo is decoded,
 * cropped and re-encoded in the browser (which drops EXIF and GPS data) and kept only in
 * memory. It stays on the crop view until a read succeeds, so a failed read can be tried
 * again or cropped differently; it is let go when it is replaced, once it has been read, and
 * when the panel leaves the page. Each view marks its main control with `data-main-control` for `MathInput.focus()`.
 */
export function PhotoPanel({
  single,
  onLines,
  onTypeInstead,
}: {
  single: boolean
  onLines: (lines: ReviewLine[] | null) => void
  onTypeInstead: () => void
}) {
  const { t } = useTranslation()
  const camera = useRef<HTMLInputElement>(null)
  const upload = useRef<HTMLInputElement>(null)
  const [image, setImage] = useState<ImageBitmap | null>(null)
  const [imageKey, setImageKey] = useState(0)
  const [preview, setPreview] = useState<string | null>(null)
  // A failure outside the transcription (opening or turning the photo). Kept as state, so the
  // object is stable across renders and its alert is focused once.
  const [localError, setLocalError] = useState<Phase | null>(null)
  const { phase, run, reset } = useTranscription()
  // Counts photo picks, so a slow load that finishes after a newer one is dropped.
  const loads = useRef(0)

  // The bitmap on screen, closed when the panel unmounts; and whether it is still mounted.
  const current = useRef<ImageBitmap | null>(null)
  const mounted = useRef(true)
  useEffect(() => {
    mounted.current = true
    return () => {
      mounted.current = false
      current.current?.close()
      current.current = null
    }
  }, [])

  const show = (next: ImageBitmap | null) => {
    if (current.current && current.current !== next) current.current.close()
    current.current = next
    setImage(next)
    if (next) setImageKey((k) => k + 1)
  }

  useEffect(
    () => () => {
      if (preview) URL.revokeObjectURL(preview)
    },
    [preview],
  )

  const startOver = () => {
    onLines(null)
    reset()
    show(null)
    setPreview(null)
    setLocalError(null)
  }

  const onFile = async (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    e.target.value = ''
    if (!file) return
    startOver()
    const load = ++loads.current
    try {
      const bitmap = await loadImage(file)
      if (mounted.current && load === loads.current) show(bitmap)
      else bitmap.close()
    } catch {
      if (load === loads.current) setLocalError({ kind: 'failed', error: 'open' })
    }
  }

  const onRotate = async () => {
    if (!image) return
    try {
      const turned = await rotateQuarter(image)
      if (mounted.current && current.current === image) show(turned)
      else turned.close()
    } catch {
      setLocalError({ kind: 'failed', error: 'image' })
    }
  }

  const onCrop = async (rect: Rect) => {
    const source = image
    if (!source || phase.kind === 'reading') return
    setLocalError(null)
    const outcome = await run(async () => {
      const blob = await cropAndDownscale(source, rect)
      if (mounted.current) setPreview(URL.createObjectURL(blob))
      return blob
    })
    // Read: the photo itself is no longer needed. Failed: it stays for another try.
    if (outcome?.kind === 'review' && current.current === source) show(null)
  }

  if (phase.kind === 'review') {
    return (
      <div className="flex flex-col gap-3">
        <TranscriptionReview
          initial={phase.lines}
          single={single}
          image={preview ? { url: preview, alt: t('input.photo.croppedAlt') } : undefined}
          retakeLabel={t('input.photo.retake')}
          onConfirm={onLines}
          onUnconfirm={() => onLines(null)}
          onRetake={startOver}
        />
        <div>
          <TypeInstead onClick={onTypeInstead} />
        </div>
      </div>
    )
  }

  if (image) {
    return (
      <div className="flex flex-col gap-3">
        <CropStep
          key={imageKey}
          image={image}
          busy={phase.kind === 'reading'}
          failed={phase.kind === 'failed'}
          onCrop={(rect) => void onCrop(rect)}
          onCancel={startOver}
          onRotate={() => void onRotate()}
        />
        <ReadingStatus phase={localError ?? phase} readingLabel={t('input.photo.reading')} />
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-3">
      <p className="text-muted-foreground">{t('input.photo.intro')}</p>
      <div className="flex flex-wrap items-center gap-2">
        <Button
          data-main-control
          type="button"
          className="min-h-11 px-5 aria-disabled:opacity-50"
          aria-disabled={phase.kind === 'reading' || undefined}
          onClick={() => phase.kind !== 'reading' && camera.current?.click()}
        >
          <Camera aria-hidden="true" />
          {t('input.photo.take')}
        </Button>
        <Button
          type="button"
          variant="outline"
          className="min-h-11 aria-disabled:opacity-50"
          aria-disabled={phase.kind === 'reading' || undefined}
          onClick={() => phase.kind !== 'reading' && upload.current?.click()}
        >
          <ImageUp aria-hidden="true" />
          {t('input.photo.upload')}
        </Button>
        <TypeInstead onClick={onTypeInstead} />
      </div>
      <input
        ref={camera}
        type="file"
        accept={ACCEPT}
        capture="environment"
        hidden
        data-testid="photo-camera"
        onChange={onFile}
      />
      <input
        ref={upload}
        type="file"
        accept={ACCEPT}
        hidden
        data-testid="photo-upload"
        onChange={onFile}
      />
      <ReadingStatus phase={localError ?? phase} readingLabel={t('input.photo.reading')} />
    </div>
  )
}
