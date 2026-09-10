import Link from "next/link"
import type { ReactNode } from "react"

export function PublicShell({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top_left,#d9f5ec,transparent_36%),radial-gradient(circle_at_90%_10%,#e8eefc,transparent_28%),linear-gradient(to_bottom,#fbfffd,#f5f7f9)] text-slate-950">
      <header className="sticky top-0 z-30 border-b border-white/70 bg-white/75 backdrop-blur-xl">
        <div className="mx-auto flex w-full max-w-5xl items-center justify-between gap-3 px-5 py-4">
          <Link href="/" aria-label="Отклик — на главную" className="flex items-center gap-2 text-xl font-semibold tracking-tight text-teal-950">
            <span className="flex size-9 items-center justify-center rounded-xl bg-teal-700 text-base text-white shadow-sm">О</span>
            <span>Отклик</span>
          </Link>
          <nav aria-label="Основная навигация" className="flex items-center gap-1 sm:gap-2">
            <Link href="/appeal/new" className="hidden rounded-lg px-3 py-2 text-sm font-medium text-slate-700 hover:bg-white sm:block">Обратиться</Link>
            <Link href="/appeal/check" className="rounded-lg px-3 py-2 text-sm font-medium text-slate-700 hover:bg-white">Проверить</Link>
            <span className="hidden rounded-full bg-teal-50 px-3 py-1.5 text-xs font-medium text-teal-800 ring-1 ring-teal-100 md:block">Без регистрации</span>
          </nav>
        </div>
      </header>
      <main className="mx-auto w-full max-w-5xl px-4 pb-16 sm:px-5">{children}</main>
      <footer className="border-t border-slate-200/70 bg-white/50"><div className="mx-auto flex max-w-5xl flex-col gap-2 px-5 py-7 text-xs leading-5 text-slate-500 sm:flex-row sm:items-center sm:justify-between"><p>Анонимное обращение без аккаунта заявителя.</p><p>Не сообщайте номер обращения посторонним.</p></div></footer>
    </div>
  )
}
