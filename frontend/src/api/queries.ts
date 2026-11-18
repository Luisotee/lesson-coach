import { QueryClient, queryOptions, useMutation, useQueries, useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { ApiError, getJson, postJson } from '@/api/client'
import type {
  CheckWorkingRequest,
  CheckWorkingResult,
  MistakeRequest,
  MistakeResult,
  Pack,
  TopicSummary,
} from '@/api/types'
import { findLanguage } from '@/i18n/languages'

export function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        // Packs are static per deploy; refetching on focus would only cost requests.
        staleTime: Infinity,
        refetchOnWindowFocus: false,
        // A 404 is an answer, not a hiccup.
        retry: (count, error) => !(error instanceof ApiError && error.status < 500) && count < 2,
      },
    },
  })
}

/** The active UI language's code, as the API expects it. */
export function useApiLang(): string {
  const { i18n } = useTranslation()
  return findLanguage(i18n.resolvedLanguage ?? i18n.language).code
}

export function useTopics() {
  const lang = useApiLang()
  return useQuery({
    queryKey: ['topics', lang],
    queryFn: ({ signal }) =>
      getJson<TopicSummary[]>(`/api/topics?lang=${encodeURIComponent(lang)}`, signal),
  })
}

/** The topic pack in the UI language; the API falls back to English and `pack.lang` says so. */
function packQuery(id: string, lang: string) {
  return queryOptions({
    queryKey: ['pack', id, lang],
    queryFn: ({ signal }) =>
      getJson<Pack>(
        `/api/topics/${encodeURIComponent(id)}?lang=${encodeURIComponent(lang)}`,
        signal,
      ),
    // A language switch keeps the same topic's pack on screen until the new one arrives, so the
    // page isn't unmounted (the teacher's working, check result and open hints survive).
    // Never another topic's pack.
    placeholderData: (previous, previousQuery) =>
      previousQuery?.queryKey[1] === id ? previous : undefined,
  })
}

export function usePack(id: string) {
  return useQuery(packQuery(id, useApiLang()))
}

/** Every listed topic's pack, in the order /api/topics gives them. */
export function usePacks(ids: readonly string[]) {
  const lang = useApiLang()
  return useQueries({ queries: ids.map((id) => packQuery(id, lang)) })
}

export function useMistake() {
  return useMutation({
    mutationFn: (body: MistakeRequest) => postJson<MistakeResult>('/api/mistake', body),
  })
}

export function useCheckWorking() {
  return useMutation({
    mutationFn: (body: CheckWorkingRequest) =>
      postJson<CheckWorkingResult>('/api/check-working', body),
  })
}

export function isNotFound(error: unknown): boolean {
  return error instanceof ApiError && error.status === 404
}

/** A topic's title in the UI language: from /api/topics, or the built-in name until it loads. */
export function useTopicTitle(): (id: string) => string {
  const { t } = useTranslation()
  const topics = useTopics()
  return (id) => topics.data?.find((x) => x.id === id)?.title ?? t(`topics.${id}.title`)
}
