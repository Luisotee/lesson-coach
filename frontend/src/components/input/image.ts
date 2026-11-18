import type { Rect, Size } from '@/components/input/crop'

/** The API takes up to 5 MB; stay well under it. */
export const MAX_UPLOAD_BYTES = 4 * 1024 * 1024
/** Longest edge sent for transcription. Vision models scale larger images down anyway. */
export const MAX_EDGE = 1600

/** Scales a size down (never up) so its longest edge is at most `max`. */
export function fitWithin(size: Size, max: number): Size {
  const scale = Math.min(1, max / Math.max(size.w, size.h))
  return { w: Math.max(1, Math.round(size.w * scale)), h: Math.max(1, Math.round(size.h * scale)) }
}

/** Opens a photo, applying its EXIF orientation. Throws when the browser can't decode it. */
export async function loadImage(file: Blob): Promise<ImageBitmap> {
  return createImageBitmap(file, { imageOrientation: 'from-image' })
}

/** Turns an image a quarter turn clockwise. Returns a new bitmap; the caller closes the old one. */
export async function rotateQuarter(image: ImageBitmap): Promise<ImageBitmap> {
  const canvas = document.createElement('canvas')
  canvas.width = image.height
  canvas.height = image.width
  const ctx = canvas.getContext('2d')
  if (!ctx) throw new Error('No canvas')
  ctx.translate(canvas.width, 0)
  ctx.rotate(Math.PI / 2)
  ctx.drawImage(image, 0, 0)
  return createImageBitmap(canvas)
}

export type Encoder = (canvas: HTMLCanvasElement, type: string, quality: number) => Promise<Blob>

export const canvasEncoder: Encoder = (canvas, type, quality) =>
  new Promise((resolve, reject) =>
    canvas.toBlob((b) => (b ? resolve(b) : reject(new Error('Encoding failed'))), type, quality),
  )

/**
 * Crops and downscales a photo to a JPEG for upload. Re-encoding through a canvas drops every
 * metadata block (EXIF, GPS). Lowers the quality, then the size, until it is under the limit.
 */
export async function cropAndDownscale(
  image: CanvasImageSource & { width: number; height: number },
  crop: Rect,
  { maxEdge = MAX_EDGE, maxBytes = MAX_UPLOAD_BYTES, encode = canvasEncoder } = {},
): Promise<Blob> {
  let edge = maxEdge
  let quality = 0.85
  for (let attempt = 0; attempt < 6; attempt++) {
    const out = fitWithin({ w: crop.w, h: crop.h }, edge)
    const canvas = document.createElement('canvas')
    canvas.width = out.w
    canvas.height = out.h
    const ctx = canvas.getContext('2d')
    if (!ctx) throw new Error('No canvas')
    ctx.fillStyle = '#ffffff'
    ctx.fillRect(0, 0, out.w, out.h)
    ctx.drawImage(image, crop.x, crop.y, crop.w, crop.h, 0, 0, out.w, out.h)
    const blob = await encode(canvas, 'image/jpeg', quality)
    if (blob.size <= maxBytes) return blob
    if (quality > 0.6) quality -= 0.15
    else edge = Math.round(edge * 0.75)
  }
  throw new Error('Image too large')
}
