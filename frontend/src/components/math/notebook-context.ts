import { createContext } from 'react'

export const NotebookContext = createContext<{ writeOn: boolean; numbered: boolean }>({
  writeOn: false,
  numbered: false,
})
