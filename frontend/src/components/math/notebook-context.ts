import { createContext } from 'react'

export const NotebookContext = createContext<{ writeOn: boolean }>({ writeOn: false })
