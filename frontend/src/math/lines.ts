import type { WorkingLine } from '@/api/types'
import type { Step } from '@/math/types'

/** API lines may carry null for an empty field; the renderer wants strings. */
export function toSteps(lines: readonly (WorkingLine | Step)[] | undefined): Step[] {
  return (lines ?? []).map((l) => ({ left: l.left ?? '', right: l.right ?? '', op: l.op ?? '' }))
}
