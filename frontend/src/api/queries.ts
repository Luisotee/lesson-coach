import { QueryClient, useMutation, useQuery } from '@tanstack/react-query'
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
export function usePack(id: string) {
  const lang = useApiLang()
  return useQuery({
    queryKey: ['pack', id, lang],
    queryFn: ({ signal }) =>
      getJson<Pack>(
        `/api/topics/${encodeURIComponent(id)}?lang=${encodeURIComponent(lang)}`,
        signal,
      ),
  })
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
