"use client"

import { Button } from "@/components/ui/button"

export function StaffHeader({
  title,
  role,
  name,
  onLogout,
}: {
  title: string
  role: string
  name: string
  onLogout: () => void
}) {
  return (
    <header className="sticky top-0 z-30 border-b border-slate-200/80 bg-white/90 px-4 py-3 backdrop-blur-xl sm:px-6">
      <div className="mx-auto flex max-w-7xl items-center justify-between gap-4">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <span className="flex size-8 shrink-0 items-center justify-center rounded-xl bg-teal-700 font-semibold text-white">О</span>
            <p className="text-xs font-semibold tracking-[0.16em] text-teal-700 uppercase">Отклик · {role}</p>
          </div>
          <h1 className="mt-1 truncate text-lg font-semibold tracking-tight text-slate-950 sm:text-xl">{title}</h1>
        </div>
        <div className="flex items-center gap-2 sm:gap-3">
          <div className="hidden text-right sm:block"><p className="max-w-48 truncate text-sm font-medium">{name}</p><p className="text-xs text-slate-500">Защищённая сессия</p></div>
          <Button type="button" variant="outline" onClick={onLogout}>Выйти</Button>
        </div>
      </div>
    </header>
  )
}
