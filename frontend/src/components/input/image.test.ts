import { expect, test, vi } from 'vitest'
import { cropAndDownscale, fitWithin } from '@/components/input/image'

test('fitWithin scales down to the longest edge and never up', () => {
  expect(fitWithin({ w: 4000, h: 3000 }, 1600)).toEqual({ w: 1600, h: 1200 })
  expect(fitWithin({ w: 900, h: 3600 }, 1600)).toEqual({ w: 400, h: 1600 })
  expect(fitWithin({ w: 800, h: 600 }, 1600)).toEqual({ w: 800, h: 600 })
})

function fakeCanvas() {
  const ctx = { fillRect: vi.fn(), drawImage: vi.fn(), fillStyle: '' }
  vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue(ctx as never)
  return ctx
}

test('cropAndDownscale draws the crop at the fitted size as JPEG', async () => {
  const ctx = fakeCanvas()
  const sizes: [number, number, string, number][] = []
  const encode = vi.fn(async (c: HTMLCanvasElement, type: string, q: number) => {
    sizes.push([c.width, c.height, type, q])
    return new Blob(['x'])
  })
  const image = { width: 4000, height: 3000 } as unknown as HTMLCanvasElement
  await cropAndDownscale(image, { x: 100, y: 200, w: 3200, h: 1600 }, { encode })
  expect(sizes).toEqual([[1600, 800, 'image/jpeg', 0.85]])
  expect(ctx.drawImage).toHaveBeenCalledWith(image, 100, 200, 3200, 1600, 0, 0, 1600, 800)
})

test('cropAndDownscale lowers quality, then size, until under the limit', async () => {
  fakeCanvas()
  const calls: [number, number][] = []
  const encode = vi.fn(async (c: HTMLCanvasElement, _t: string, q: number) => {
    calls.push([c.width, Math.round(q * 100)])
    return new Blob([new Uint8Array(calls.length < 4 ? 2000 : 10)])
  })
  const image = { width: 2000, height: 2000 } as unknown as HTMLCanvasElement
  const blob = await cropAndDownscale(
    image,
    { x: 0, y: 0, w: 2000, h: 2000 },
    { encode, maxBytes: 100 },
  )
  expect(blob.size).toBe(10)
  expect(calls).toEqual([
    [1600, 85],
    [1600, 70],
    [1600, 55],
    [1200, 55],
  ])
})

test('cropAndDownscale gives up rather than send an oversized image', async () => {
  fakeCanvas()
  const encode = async () => new Blob([new Uint8Array(500)])
  const image = { width: 10, height: 10 } as unknown as HTMLCanvasElement
  await expect(
    cropAndDownscale(image, { x: 0, y: 0, w: 10, h: 10 }, { encode, maxBytes: 100 }),
  ).rejects.toThrow()
})
