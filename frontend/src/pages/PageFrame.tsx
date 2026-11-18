import type { ReactNode } from 'react'

/** The common page column with its <h1>. */
export function PageFrame({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="mx-auto flex max-w-[1200px] flex-col gap-6 px-4 py-10 sm:px-6">
      <h1 className="text-4xl font-bold tracking-tight sm:text-5xl">{title}</h1>
      {children}
    </div>
  )
}
