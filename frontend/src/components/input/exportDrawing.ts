import { getStroke } from 'perfect-freehand'
import type { Rect } from '@/components/input/crop'
import { canvasEncoder, fitWithin, type Encoder } from '@/components/input/image'
import type { Stroke } from '@/components/input/strokes'

/** Pen size in CSS px on the board. */
export const PEN_SIZE = 5

export function strokeOptions(stroke: Stroke) {
  return {
    size: PEN_SIZE,
    thinning: 0.55,
    smoothing: 0.5,
    streamline: 0.4,
    simulatePressure: !stroke.pressure,
  }
}

/** The outline of a stroke as a canvas path. */
export function strokePath(stroke: Stroke): Path2D {
  const outline = getStroke(stroke.points, strokeOptions(stroke))
  const path = new Path2D()
  if (outline.length === 0) return path
  path.moveTo(outline[0][0], outline[0][1])
  for (const [x, y] of outline.slice(1)) path.lineTo(x, y)
  path.closePath()
  return path
}

/** The box around every point, grown by `pad`; null for no strokes. */
export function strokeBounds(strokes: Stroke[], pad: number): Rect | null {
  let minX = Infinity
  let minY = Infinity
  let maxX = -Infinity
  let maxY = -Infinity
  for (const s of strokes)
    for (const [x, y] of s.points) {
      minX = Math.min(minX, x)
      minY = Math.min(minY, y)
      maxX = Math.max(maxX, x)
      maxY = Math.max(maxY, y)
    }
  if (minX === Infinity) return null
  return { x: minX - pad, y: minY - pad, w: maxX - minX + 2 * pad, h: maxY - minY + 2 * pad }
}

/** Longest edge of the exported drawing. */
export const EXPORT_MAX_EDGE = 1600

/**
 * The drawing as a PNG for transcription: only the ink, black on white, cropped to the
 * strokes, without the squared paper (grid lines can be misread as minus signs).
 */
export async function exportDrawing(strokes: Stroke[], encode: Encoder = canvasEncoder): Promise<Blob> {
  const box = strokeBounds(strokes, 24)
  if (!box) throw new Error('Nothing drawn')
  // Draw at 2x for a thin pen, but never past the size limit.
  const out = fitWithin({ w: box.w * 2, h: box.h * 2 }, EXPORT_MAX_EDGE)
  const scale = out.w / box.w
  const canvas = document.createElement('canvas')
  canvas.width = out.w
  canvas.height = out.h
  const ctx = canvas.getContext('2d')
  if (!ctx) throw new Error('No canvas')
  ctx.fillStyle = '#ffffff'
  ctx.fillRect(0, 0, out.w, out.h)
  ctx.setTransform(scale, 0, 0, scale, -box.x * scale, -box.y * scale)
  ctx.fillStyle = '#000000'
  for (const s of strokes) ctx.fill(strokePath(s))
  return encode(canvas, 'image/png', 1)
}
