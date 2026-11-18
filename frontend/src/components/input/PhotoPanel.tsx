import { Camera, ImageUp } from 'lucide-react'
import { useEffect, useImperativeHandle, useRef, useState, type ChangeEvent, type Ref } from 'react'
import { useTranslation } from 'react-i18next'
import { CropStep } from '@/components/input/CropStep'
import type { Rect } from '@/components/input/crop'
import { cropAndDownscale, loadImage, rotateQuarter } from '@/components/input/image'
import { ReadingStatus, TypeInstead } from '@/components/input/Reading'
import { TranscriptionReview } from '@/components/input/TranscriptionReview'
import type { ReviewLine } from '@/components/input/types'
import { useTranscription } from '@/components/input/useTranscription'
import type { PanelHandle } from '@/components/input/WritePanel'
import { Button } from '@/components/ui/button'

const ACCEPT = 'image/png,image/jpeg,image/webp'

/**
 * Take or upload a photo, crop it, have it read, confirm the lines. The photo is decoded,
 * cropped and re-encoded in the browser (which drops EXIF and GPS data) and kept only in
 * memory; it is let go when the panel leaves the page.
 */
export function PhotoPanel({
  single,
  onLines,
  onTypeInstead,
  ref,
}: {
  single: boolean
  onLines: (lines: ReviewLine[] | null) => void
  onTypeInstead: () => void
  ref?: Ref<PanelHandle>
}) {
  const { t } = useTranslation()
  const camera = useRef<HTMLInputElement>(null)
  const upload = useRef<HTMLInputElement>(null)
  const cameraButton = useRef<HTMLButtonElement>(null)
  const [image, setImage] = useState<ImageBitmap | null>(null)
  const [imageKey, setImageKey] = useState(0)
  const [preview, setPreview] = useState<string | null>(null)
  const [openError, setOpenError] = useState(false)
  const { phase, run, reset } = useTranscription()

  useImperativeHandle(ref, () => ({ focus: () => cameraButton.current?.focus() }))

  // Let go of the photo and its preview when they are replaced or the panel unmounts.
  useEffect(() => () => image?.close(), [image])
  useEffect(
    () => () => {
      if (preview) URL.revokeObjectURL(preview)
    },
    [preview],
  )

  const startOver = () => {
    onLines(null)
    reset()
    setImage(null)
    setPreview(null)
    setOpenError(false)
  }

  const onFile = async (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    e.target.value = ''
    if (!file) return
    startOver()
    try {
      setImage(await loadImage(file))
      setImageKey((k) => k + 1)
    } catch {
      setOpenError(true)
    }
  }

  const onCrop = (rect: Rect) => {
    const source = image
    if (!source) return
    void run(async () => {
      const blob = await cropAndDownscale(source, rect)
      setPreview(URL.createObjectURL(blob))
      return blob
    })
    setImage(null)
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
      <CropStep
        key={imageKey}
        image={image}
        onCrop={onCrop}
        onCancel={startOver}
        onRotate={async () => {
          const turned = await rotateQuarter(image)
          setImage(turned)
          setImageKey((k) => k + 1)
        }}
      />
    )
  }

  return (
    <div className="flex flex-col gap-3">
      <p className="text-muted-foreground">{t('input.photo.intro')}</p>
      <div className="flex flex-wrap items-center gap-2">
        <Button
          ref={cameraButton}
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
      {preview && phase.kind === 'reading' && (
        <img
          src={preview}
          alt={t('input.photo.croppedAlt')}
          className="max-h-48 w-auto max-w-full self-start rounded-xl border border-line"
        />
      )}
      <ReadingStatus
        phase={openError ? { kind: 'failed', message: t('input.error.open') } : phase}
        readingLabel={t('input.photo.reading')}
      />
    </div>
  )
}
