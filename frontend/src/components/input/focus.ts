/**
 * Moves focus to `el` only while the teacher is still in this input, or nowhere: a result that
 * arrives late must not pull focus out of another field the teacher has moved on to.
 */
export function focusIfHere(el: HTMLElement | null) {
  if (!el) return
  const active = document.activeElement
  const scope = el.closest('[role="tabpanel"]') ?? el.closest('fieldset') ?? el.parentElement
  if (!active || active === document.body || scope?.contains(active)) el.focus()
}
