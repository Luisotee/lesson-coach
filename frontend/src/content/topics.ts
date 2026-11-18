/** Topic ids shared with the backend and content packs. T8 reads the list from /api/topics. */
export const TOPIC_IDS = ['negative-numbers', 'fractions', 'linear-equations'] as const
export type TopicId = (typeof TOPIC_IDS)[number]

/** Practice problems per topic (PLAN: 8 from OATutor-Content). */
export const PRACTICE_COUNT = 8

export function isTopicId(id: string | undefined): id is TopicId {
  return TOPIC_IDS.includes(id as TopicId)
}
