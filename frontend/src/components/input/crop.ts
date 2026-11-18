/** A rectangle in some pixel space. */
export interface Rect {
  x: number
  y: number
  w: number
  h: number
}

export type Handle = 'nw' | 'ne' | 'sw' | 'se'

export interface Size {
  w: number
  h: number
}

/** Keeps a rectangle inside the bounds, at least `min` wide and tall. */
export function clampRect(r: Rect, bounds: Size, min = 1): Rect {
  const w = Math.min(Math.max(r.w, min), bounds.w)
  const h = Math.min(Math.max(r.h, min), bounds.h)
  const x = Math.min(Math.max(r.x, 0), bounds.w - w)
  const y = Math.min(Math.max(r.y, 0), bounds.h - h)
  return { x, y, w, h }
}

/** Moves without resizing; stops at the edges. */
export function moveRect(r: Rect, dx: number, dy: number, bounds: Size): Rect {
  return clampRect({ ...r, x: r.x + dx, y: r.y + dy }, bounds)
}

/** Drags one corner; the opposite corner stays put. */
export function resizeRect(
  r: Rect,
  handle: Handle,
  dx: number,
  dy: number,
  bounds: Size,
  min: number,
): Rect {
  let left = r.x
  let top = r.y
  let right = r.x + r.w
  let bottom = r.y + r.h
  if (handle === 'nw' || handle === 'sw') left = Math.min(Math.max(left + dx, 0), right - min)
  else right = Math.max(Math.min(right + dx, bounds.w), left + min)
  if (handle === 'nw' || handle === 'ne') top = Math.min(Math.max(top + dy, 0), bottom - min)
  else bottom = Math.max(Math.min(bottom + dy, bounds.h), top + min)
  return { x: left, y: top, w: right - left, h: bottom - top }
}

/** Grows or shrinks from the bottom-right corner, for the keyboard (Shift + arrows). */
export function growRect(r: Rect, dw: number, dh: number, bounds: Size, min: number): Rect {
  return resizeRect(r, 'se', dw, dh, bounds, min)
}

/** Scales a rectangle shown at `scale` (display px per image px) back to image pixels, rounded inward to whole pixels. */
export function displayToImage(r: Rect, scale: number, image: Size): Rect {
  const x = Math.max(0, Math.round(r.x / scale))
  const y = Math.max(0, Math.round(r.y / scale))
  const w = Math.min(image.w - x, Math.round(r.w / scale))
  const h = Math.min(image.h - y, Math.round(r.h / scale))
  return { x, y, w: Math.max(1, w), h: Math.max(1, h) }
}

/** The starting crop: the whole image less a small margin. */
export function initialCrop(bounds: Size, margin = 0.05): Rect {
  return {
    x: bounds.w * margin,
    y: bounds.h * margin,
    w: bounds.w * (1 - 2 * margin),
    h: bounds.h * (1 - 2 * margin),
  }
}
