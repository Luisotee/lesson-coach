import { Check, Expand, RotateCw, X } from 'lucide-react'
import { useEffect, useId, useRef, useState, type KeyboardEvent, type PointerEvent } from 'react'
import { useTranslation } from 'react-i18next'
import {
  growRect,
  initialCrop,
  moveRect,
  resizeRect,
  type Handle,
  type Rect,
} from '@/components/input/crop'
import { Button } from '@/components/ui/button'

const HANDLES: Handle[] = ['nw', 'ne', 'sw', 'se']
const handlePos: Record<Handle, string> = {
  nw: 'left-0 top-0 items-start justify-start cursor-nwse-resize',
  ne: 'right-0 top-0 items-start justify-end cursor-nesw-resize',
  sw: 'left-0 bottom-0 items-end justify-start cursor-nesw-resize',
  se: 'right-0 bottom-0 items-end justify-end cursor-nwse-resize',
}

/**
 * Crop (and turn) a photo before it is read. The crop box is dragged by its body or corners,
 * or moved with the arrow keys and resized with Shift + arrows. Coordinates are image pixels.
 * Give it a new `key` with each new (or turned) image, so the crop starts fresh.
 */
export function CropStep({
  image,
  onRotate,
  onCrop,
  onCancel,
}: {
  image: ImageBitmap
  onRotate: () => void
  onCrop: (rect: Rect) => void
  onCancel: () => void
}) {
  const { t } = useTranslation()
  const helpId = useId()
  const canvas = useRef<HTMLCanvasElement>(null)
  const frame = useRef<HTMLDivElement>(null)
  const bounds = { w: image.width, h: image.height }
  const [rect, setRect] = useState<Rect>(() => initialCrop(bounds))
  const [scale, setScale] = useState(1)
  const drag = useRef<{
    id: number
    handle: Handle | 'move'
    x: number
    y: number
    start: Rect
  } | null>(null)
  const min = Math.max(8, Math.min(bounds.w, bounds.h) * 0.05)

  useEffect(() => {
    const el = canvas.current
    const box = frame.current
    if (!el || !box) return
    const fit = () => {
      const maxH = Math.max(240, window.innerHeight * 0.6)
      const s = Math.min(box.clientWidth / image.width, maxH / image.height, 1)
      el.width = Math.round(image.width * s)
      el.height = Math.round(image.height * s)
      el.getContext('2d')?.drawImage(image, 0, 0, el.width, el.height)
      setScale(s)
    }
    fit()
    if (typeof ResizeObserver === 'undefined') return
    const observer = new ResizeObserver(fit)
    observer.observe(box)
    return () => observer.disconnect()
  }, [image])

  const startDrag = (handle: Handle | 'move', e: PointerEvent<HTMLElement>) => {
    e.preventDefault()
    e.stopPropagation()
    e.currentTarget.setPointerCapture(e.pointerId)
    drag.current = { id: e.pointerId, handle, x: e.clientX, y: e.clientY, start: rect }
  }
  const onPointerMove = (e: PointerEvent<HTMLElement>) => {
    const d = drag.current
    if (!d || d.id !== e.pointerId) return
    const dx = (e.clientX - d.x) / scale
    const dy = (e.clientY - d.y) / scale
    setRect(
      d.handle === 'move'
        ? moveRect(d.start, dx, dy, bounds)
        : resizeRect(d.start, d.handle, dx, dy, bounds, min),
    )
  }
  const onPointerUp = () => {
    drag.current = null
  }

  const onKeyDown = (e: KeyboardEvent) => {
    const step = Math.max(1, Math.round(Math.min(bounds.w, bounds.h) * 0.02))
    const dirs: Record<string, [number, number]> = {
      ArrowLeft: [-step, 0],
      ArrowRight: [step, 0],
      ArrowUp: [0, -step],
      ArrowDown: [0, step],
    }
    const d = dirs[e.key]
    if (!d) return
    e.preventDefault()
    setRect(
      e.shiftKey ? growRect(rect, d[0], d[1], bounds, min) : moveRect(rect, d[0], d[1], bounds),
    )
  }

  const pct = (v: number, of: number) => Math.round((v / of) * 100)
  const description = t('input.photo.cropState', {
    w: pct(rect.w, bounds.w),
    h: pct(rect.h, bounds.h),
    x: pct(rect.x, bounds.w),
    y: pct(rect.y, bounds.h),
  })

  return (
    <div className="flex flex-col gap-3">
      <p id={helpId} className="text-muted-foreground">
        {t('input.photo.cropHelp')}
      </p>
      <div ref={frame} dir="ltr" className="w-full">
        <div
          className="relative mx-auto w-fit touch-none overflow-hidden rounded-lg select-none"
          onPointerMove={onPointerMove}
          onPointerUp={onPointerUp}
          onPointerCancel={onPointerUp}
        >
          <canvas
            ref={canvas}
            role="img"
            aria-label={t('input.photo.photoAlt')}
            className="block rounded-lg"
          />
          <div
            role="group"
            tabIndex={0}
            aria-label={t('input.photo.cropBox')}
            aria-describedby={helpId}
            aria-description={description}
            data-testid="crop-box"
            className="absolute cursor-move border-2 border-white shadow-[0_0_0_9999px_rgba(23,43,83,0.55)] outline-none ring-navy focus-visible:ring-4"
            style={{
              left: rect.x * scale,
              top: rect.y * scale,
              width: rect.w * scale,
              height: rect.h * scale,
            }}
            onPointerDown={(e) => startDrag('move', e)}
            onKeyDown={onKeyDown}
          >
            {HANDLES.map((h) => (
              <span
                key={h}
                aria-hidden="true"
                data-handle={h}
                className={`absolute flex size-11 ${handlePos[h]}`}
                onPointerDown={(e) => startDrag(h, e)}
              >
                <span className="m-[-2px] size-5 rounded-full border-2 border-navy bg-white" />
              </span>
            ))}
          </div>
        </div>
      </div>
      <p className="sr-only" aria-live="polite">
        {description}
      </p>
      <div className="flex flex-wrap gap-2">
        <Button type="button" className="min-h-11 px-5" onClick={() => onCrop(rect)}>
          <Check aria-hidden="true" />
          {t('input.photo.useCrop')}
        </Button>
        <Button
          type="button"
          variant="outline"
          className="min-h-11"
          onClick={() => onCrop({ x: 0, y: 0, ...bounds })}
        >
          <Expand aria-hidden="true" />
          {t('input.photo.useWhole')}
        </Button>
        <Button type="button" variant="outline" className="min-h-11" onClick={onRotate}>
          <RotateCw aria-hidden="true" />
          {t('input.photo.rotate')}
        </Button>
        <Button type="button" variant="outline" className="min-h-11" onClick={onCancel}>
          <X aria-hidden="true" />
          {t('input.photo.other')}
        </Button>
      </div>
    </div>
  )
}
