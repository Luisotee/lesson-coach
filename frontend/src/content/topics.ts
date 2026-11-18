/** Topic ids shared with the backend and content packs. T8 reads the list from /api/topics. */
export const TOPIC_IDS = ['negative-numbers', 'fractions', 'linear-equations'] as const
export type TopicId = (typeof TOPIC_IDS)[number]

/** Practice problems per topic (PLAN: 8 from OATutor-Content). */
export const PRACTICE_COUNT = 8

export function isTopicId(id: string | undefined): id is TopicId {
  return TOPIC_IDS.includes(id as TopicId)
}

/** Parses a 1-based practice problem number; anything else is not a page. */
export function problemNumber(raw: string | undefined): number | null {
  if (!raw || !/^\d+$/.test(raw)) return null
  const n = Number(raw)
  return n >= 1 && n <= PRACTICE_COUNT ? n : null
}

/** A sample of each topic's math for its card: presentation only, drawn by hand. */
export const TOPIC_GLYPHS: Record<TopicId, { expr: string; tone: string }> = {
  'negative-numbers': { expr: '-3 + 5', tone: 'bg-[#eef1f4] text-navy' },
  fractions: { expr: '1/2 + 1/3', tone: 'bg-[#fffbeb] text-[#92400e]' },
  'linear-equations': { expr: '3*x + 5 = 20', tone: 'bg-paleblue/60 text-navy' },
}
