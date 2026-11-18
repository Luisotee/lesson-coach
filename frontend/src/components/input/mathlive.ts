import type { MathfieldElement } from 'mathlive'

let loading: Promise<typeof MathfieldElement> | null = null

/**
 * Loads MathLive on first use, so it stays out of the main bundle. Its fonts come from our
 * own build (the CSS import), so MathLive fetches none at run time, and it plays no sounds.
 */
export function loadMathLive(): Promise<typeof MathfieldElement> {
  loading ??= Promise.all([import('mathlive'), import('mathlive/fonts.css')])
    .then(([ml]) => {
      ml.MathfieldElement.fontsDirectory = null
      ml.MathfieldElement.soundsDirectory = null
      return ml.MathfieldElement
    })
    .catch((e: unknown) => {
      loading = null
      throw e
    })
  return loading
}
