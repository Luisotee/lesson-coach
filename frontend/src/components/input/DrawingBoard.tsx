import { Eraser, Redo2, Undo2 } from 'lucide-react'
import {
  useEffect,
  useRef,
  useState,
  type Dispatch,
  type PointerEvent,
  type ReactNode,
} from 'react'
import { useTranslation } from 'react-i18next'
import { strokePath } from '@/components/input/exportDrawing'
import {
  canRedo,
  canUndo,
  visibleStrokes,
  type History,
  type HistoryEvent,
  type Point,
  type Stroke,
} from '@/components/input/strokes'
import { Button } from '@/components/ui/button'

/**
 * A toolbar button that stays focusable when it can't act (aria-disabled), so focus isn't lost
 * when, say, the last stroke is undone.
 */
function ToolButton({
  off,
  onClick,
  children,
}: {
  off: boolean
  onClick: () => void
  children: ReactNode
}) {
  return (
    <Button
      type="button"
      variant="outline"
      className="min-h-11 aria-disabled:opacity-50"
      aria-disabled={off || undefined}
      onClick={() => !off && onClick()}
    >
      {children}
    </Button>
  )
}

/** Navy ink, as on the worked examples. */
const INK = '#172b53'

/**
 * Squared paper to write on with a finger, pen or mouse. Strokes are pressure-aware
 * (perfect-freehand) and live only in memory. The canvas can't be used from the keyboard, so
 * the panel around it always offers typing instead; the board says in text how much is on it.
 */
export function DrawingBoard({
  label,
  history,
  dispatch,
  rows = 6,
}: {
  label: string
  history: History
  dispatch: Dispatch<HistoryEvent>
  /** Height in grid squares (22 px each). */
  rows?: number
}) {
  const { t } = useTranslation()
  const canvas = useRef<HTMLCanvasElement>(null)
  const current = useRef<{ id: number; stroke: Stroke } | null>(null)
  const frame = useRef(0)
  const [size, setSize] = useState({ w: 0, h: rows * 44 })
  const [announcement, setAnnouncement] = useState('')
  const strokes = visibleStrokes(history)

  // Match the canvas to its box and the screen's pixel density.
  useEffect(() => {
    const el = canvas.current
    if (!el || typeof ResizeObserver === 'undefined') return
    const observer = new ResizeObserver(([entry]) => {
      const { width, height } = entry.contentRect
      setSize({ w: Math.round(width), h: Math.round(height) })
    })
    observer.observe(el)
    return () => observer.disconnect()
  }, [])

  const paint = () => {
    const el = canvas.current
    const ctx = el?.getContext('2d')
    if (!el || !ctx) return
    const dpr = window.devicePixelRatio || 1
    if (el.width !== size.w * dpr || el.height !== size.h * dpr) {
      el.width = size.w * dpr
      el.height = size.h * dpr
    }
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
    ctx.clearRect(0, 0, size.w, size.h)
    ctx.fillStyle = INK
    for (const s of strokes) ctx.fill(strokePath(s))
    if (current.current) ctx.fill(strokePath(current.current.stroke))
  }
  // Repaint whenever the strokes or the size change.
  useEffect(paint)

  const point = (e: PointerEvent<HTMLCanvasElement> | globalThis.PointerEvent): Point => {
    const box = canvas.current!.getBoundingClientRect()
    return [e.clientX - box.left, e.clientY - box.top, e.pointerType === 'pen' ? e.pressure : 0.5]
  }

  const onPointerDown = (e: PointerEvent<HTMLCanvasElement>) => {
    if (current.current || (e.pointerType === 'mouse' && e.button !== 0)) return
    e.preventDefault()
    e.currentTarget.setPointerCapture(e.pointerId)
    current.current = {
      id: e.pointerId,
      stroke: { points: [point(e)], pressure: e.pointerType === 'pen' },
    }
    paint()
  }
  const onPointerMove = (e: PointerEvent<HTMLCanvasElement>) => {
    const c = current.current
    if (!c || c.id !== e.pointerId) return
    const events = e.nativeEvent.getCoalescedEvents?.() ?? []
    for (const ev of events.length ? events : [e.nativeEvent]) c.stroke.points.push(point(ev))
    cancelAnimationFrame(frame.current)
    frame.current = requestAnimationFrame(paint)
  }
  const onPointerUp = (e: PointerEvent<HTMLCanvasElement>) => {
    const c = current.current
    if (!c || c.id !== e.pointerId) return
    current.current = null
    dispatch({ type: 'add', stroke: c.stroke })
  }

  const act = (type: 'undo' | 'redo' | 'clear') => {
    dispatch({ type })
    setAnnouncement(t(`input.write.did.${type}`))
  }

  const status =
    strokes.length === 0
      ? t('input.write.empty')
      : t('input.write.strokes', { count: strokes.length })

  return (
    <div
      role="group"
      aria-label={label}
      className="flex flex-col gap-2"
      onKeyDown={(e) => {
        if (!(e.ctrlKey || e.metaKey)) return
        const key = e.key.toLowerCase()
        if (key === 'z' && !e.shiftKey && canUndo(history)) act('undo')
        else if (((key === 'z' && e.shiftKey) || key === 'y') && canRedo(history)) act('redo')
        else return
        e.preventDefault()
      }}
    >
      <div dir="ltr" className="paper overflow-hidden rounded-xl border border-input">
        <canvas
          ref={canvas}
          role="img"
          aria-label={`${label}: ${status}`}
          data-testid="drawing-canvas"
          className="block w-full cursor-crosshair touch-none select-none"
          style={{ height: rows * 44 }}
          onPointerDown={onPointerDown}
          onPointerMove={onPointerMove}
          onPointerUp={onPointerUp}
          onPointerCancel={onPointerUp}
        />
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <ToolButton off={!canUndo(history)} onClick={() => act('undo')}>
          <Undo2 aria-hidden="true" className="rtl:-scale-x-100" />
          {t('input.write.undo')}
        </ToolButton>
        <ToolButton off={!canRedo(history)} onClick={() => act('redo')}>
          <Redo2 aria-hidden="true" className="rtl:-scale-x-100" />
          {t('input.write.redo')}
        </ToolButton>
        <ToolButton off={strokes.length === 0} onClick={() => act('clear')}>
          <Eraser aria-hidden="true" />
          {t('input.write.clear')}
        </ToolButton>
        <span className="text-sm text-muted-foreground" aria-hidden="true">
          {status}
        </span>
      </div>
      <p role="status" className="sr-only">
        {announcement && `${announcement} ${status}`}
      </p>
    </div>
  )
}
