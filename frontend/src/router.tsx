import type { RouteObject } from 'react-router'
import { Shell } from '@/components/shell/Shell'
import { HomePage } from '@/pages/HomePage'
import { MistakePage } from '@/pages/MistakePage'
import { NotFoundPage } from '@/pages/NotFoundPage'
import { PracticePage } from '@/pages/PracticePage'
import { PracticeStartPage } from '@/pages/PracticeStartPage'
import { TopicPage } from '@/pages/TopicPage'

/**
 * Showcases of the math components and the math input, for development only: registered in dev,
 * and lazily imported, so the production bundle drops them.
 */
const demoRoutes: RouteObject[] = import.meta.env.DEV
  ? [
      {
        path: '/demo/math',
        lazy: async () => ({ Component: (await import('@/pages/MathDemoPage')).MathDemoPage }),
      },
      {
        path: '/demo/input',
        lazy: async () => ({ Component: (await import('@/pages/InputDemoPage')).InputDemoPage }),
      },
    ]
  : []

export const routes: RouteObject[] = [
  {
    element: <Shell />,
    children: [
      { path: '/', element: <HomePage /> },
      { path: '/topics/:id', element: <TopicPage /> },
      { path: '/mistake', element: <MistakePage /> },
      { path: '/practice', element: <PracticeStartPage /> },
      { path: '/practice/:topic/:n', element: <PracticePage /> },
      ...demoRoutes,
      { path: '*', element: <NotFoundPage /> },
    ],
  },
]
