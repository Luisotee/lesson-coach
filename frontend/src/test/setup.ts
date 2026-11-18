import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterEach } from 'vitest'
import { ready } from '@/i18n'

afterEach(cleanup)

await ready
