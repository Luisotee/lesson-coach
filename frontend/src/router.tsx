import type { RouteObject } from 'react-router'
import { Shell } from '@/components/shell/Shell'
import { HomePage } from '@/pages/HomePage'
import { MathDemoPage } from '@/pages/MathDemoPage'
import { MistakePage } from '@/pages/MistakePage'
import { NotFoundPage } from '@/pages/NotFoundPage'
import { PracticePage } from '@/pages/PracticePage'
import { TopicPage } from '@/pages/TopicPage'

export const routes: RouteObject[] = [
  {
    element: <Shell />,
    children: [
      { path: '/', element: <HomePage /> },
      { path: '/topics/:id', element: <TopicPage /> },
      { path: '/mistake', element: <MistakePage /> },
      { path: '/practice/:topic/:n', element: <PracticePage /> },
      { path: '/demo/math', element: <MathDemoPage /> },
      { path: '*', element: <NotFoundPage /> },
    ],
  },
]
