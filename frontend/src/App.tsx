import { Suspense } from 'react'
import { createBrowserRouter } from 'react-router'
import { RouterProvider } from 'react-router/dom'
import { routes } from '@/router'

const router = createBrowserRouter(routes)

export default function App() {
  // Suspense covers the first fetch of a lazy-loaded locale.
  return (
    <Suspense fallback={null}>
      <RouterProvider router={router} />
    </Suspense>
  )
}
