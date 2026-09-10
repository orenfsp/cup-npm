import Link from "next/link"
import type { ReactNode } from "react"

import { OtklikLogo } from "@/components/brand/otklik-logo"

export function PublicShell({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen bg-[#f7f8fb] text-slate-950">
      <header className="sticky top-0 z-30 border-b border-slate-200 bg-white">
        <div className="mx-auto flex w-full max-w-5xl items-center justify-between gap-3 px-5 py-4">
          <Link href="/" aria-label="Отклик — на главную" className="rounded-xl">
            <OtklikLogo size={38} />
          </Link>
          <nav aria-label="Основная навигация" className="flex items-center gap-1 sm:gap-2">
            <Link href="/appeal/new" className="hidden rounded-lg px-3 py-2 text-sm font-medium text-slate-700 hover:bg-indigo-50 hover:text-indigo-800 sm:block">Обратиться</Link>
            <Link href="/appeal/check" className="rounded-lg px-3 py-2 text-sm font-medium text-slate-700 hover:bg-indigo-50 hover:text-indigo-800">Проверить</Link>
            <span className="hidden rounded-full bg-indigo-50 px-3 py-1.5 text-xs font-medium text-indigo-800 ring-1 ring-indigo-100 md:block">Без регистрации</span>
          </nav>
        </div>
      </header>
      <main className="mx-auto w-full max-w-5xl px-4 pb-16 sm:px-5">{children}</main>
      <footer className="border-t border-slate-200 bg-white"><div className="mx-auto flex max-w-5xl flex-col gap-2 px-5 py-7 text-xs leading-5 text-slate-500 sm:flex-row sm:items-center sm:justify-between"><p>Анонимное обращение без аккаунта заявителя.</p><p>Не сообщайте номер обращения посторонним.</p></div></footer>
    </div>
  )
}
