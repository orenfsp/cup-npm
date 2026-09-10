"use client"

import {
  Inbox,
  LayoutDashboard,
  LifeBuoy,
  ListChecks,
  LogOut,
  Menu,
  Network,
  ScrollText,
  Settings,
  ShieldAlert,
  ShieldCheck,
  Tags,
  Users,
  X,
  type LucideIcon,
} from "lucide-react"
import { useState } from "react"

import { OtklikLogo } from "@/components/brand/otklik-logo"
import { Button } from "@/components/ui/button"

export type StaffNavigationItem = {
  id: string
  label: string
  active: boolean
  onSelect: () => void
}

const navigationIcons: Record<string, LucideIcon> = {
  overview: LayoutDashboard,
  appeals: Inbox,
  staff: Users,
  types: Users,
  categories: Tags,
  questions: ListChecks,
  groups: Users,
  routing: Network,
  crisis: ShieldAlert,
  support: LifeBuoy,
  audit: ScrollText,
  settings: Settings,
  workspace: LayoutDashboard,
}

function Brand() {
  return (
    <div>
      <OtklikLogo size={42} />
      <p className="mt-1 pl-[54px] text-xs text-slate-500">Защищённая платформа</p>
    </div>
  )
}

export function StaffHeader({
  title,
  role,
  name,
  onLogout,
  navigation = [],
}: {
  title: string
  role: string
  name: string
  onLogout: () => void
  navigation?: StaffNavigationItem[]
}) {
  const [mobileOpen, setMobileOpen] = useState(false)
  const workspaceItem: StaffNavigationItem = {
    id: "workspace",
    label: title,
    active: true,
    onSelect: () => undefined,
  }
  const items = navigation.length ? navigation : [workspaceItem]

  function select(item: StaffNavigationItem) {
    item.onSelect()
    setMobileOpen(false)
  }

  return (
    <>
      <aside className="fixed inset-y-0 left-0 z-40 hidden w-62 flex-col border-r border-slate-200 bg-white lg:flex">
        <div className="border-b border-slate-100 px-6 py-6">
          <Brand />
        </div>
        <div className="px-5 pb-2 pt-5">
          <p className="page-eyebrow">{role}</p>
        </div>
        <nav
          aria-label="Рабочие разделы"
          className="soft-scrollbar flex-1 space-y-1 overflow-y-auto px-3 pb-4"
        >
          {items.map((item) => {
            const Icon = navigationIcons[item.id] ?? LayoutDashboard
            return <button
              key={item.id}
              type="button"
              onClick={() => select(item)}
              aria-current={item.active ? "page" : undefined}
              className={`flex min-h-10 w-full items-center gap-2.5 rounded-xl px-3 py-2 text-left text-sm font-medium transition-colors ${
                item.active
                  ? "bg-indigo-50 text-indigo-800 ring-1 ring-indigo-100"
                  : "text-slate-600 hover:bg-slate-50 hover:text-slate-950"
              }`}
            >
              <Icon className="size-4 shrink-0" aria-hidden="true" />
              <span>{item.label}</span>
            </button>
          })}
        </nav>
        <div className="border-t border-slate-100 p-4">
          <div className="mb-3 flex items-center gap-2.5 rounded-xl bg-slate-50 p-3">
            <ShieldCheck className="size-4 shrink-0 text-indigo-600" aria-hidden="true" />
            <div className="min-w-0">
              <p className="truncate text-sm font-medium text-slate-900">{name}</p>
              <p className="text-xs text-slate-500">Защищённая сессия</p>
            </div>
          </div>
          <Button className="w-full" type="button" variant="outline" onClick={onLogout}>
            <LogOut aria-hidden="true" />
            Выйти
          </Button>
        </div>
      </aside>

      <header className="sticky top-0 z-30 border-b border-slate-200 bg-white px-4 py-3 lg:hidden">
        <div className="flex items-center justify-between gap-3">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <OtklikLogo compact size={34} />
              <div className="min-w-0"><p className="text-xs font-semibold text-indigo-700">{role}</p><h1 className="truncate text-base font-semibold text-slate-950">{title}</h1></div>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {navigation.length ? (
              <Button
                type="button"
                variant="outline"
                size="icon"
                aria-label={mobileOpen ? "Закрыть навигацию" : "Открыть навигацию"}
                aria-expanded={mobileOpen}
                onClick={() => setMobileOpen((value) => !value)}
              >
                {mobileOpen ? <X aria-hidden="true" /> : <Menu aria-hidden="true" />}
              </Button>
            ) : null}
            <Button
              type="button"
              variant="outline"
              size="icon"
              aria-label="Выйти"
              onClick={onLogout}
            >
              <LogOut aria-hidden="true" />
            </Button>
          </div>
        </div>
        {mobileOpen ? (
          <nav
            aria-label="Рабочие разделы"
            className="soft-scrollbar mt-3 max-h-[65vh] space-y-1 overflow-y-auto border-t border-slate-100 pt-3"
          >
            {navigation.map((item) => (
              <button
                key={item.id}
                type="button"
                onClick={() => select(item)}
                aria-current={item.active ? "page" : undefined}
                className={`min-h-11 w-full rounded-xl px-3 py-2 text-left text-sm font-medium ${
                  item.active
                    ? "bg-indigo-50 text-indigo-800"
                    : "text-slate-700 hover:bg-slate-50"
                }`}
              >
                {item.label}
              </button>
            ))}
          </nav>
        ) : null}
      </header>
    </>
  )
}
