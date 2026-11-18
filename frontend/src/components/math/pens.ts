export type PenVariant = 'pencil' | 'ink' | 'green'

/** Pencil grey for student work, navy ink for worked examples, green pen for corrections. */
export const penClass: Record<PenVariant, string> = {
  pencil: 'text-pencil',
  ink: 'text-ink',
  green: 'text-pen-green',
}
