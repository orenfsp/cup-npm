"use client"

import { useEffect, useState, type ReactNode } from "react"
import { useQuery, useQueryClient } from "@tanstack/react-query"
import { useRouter } from "next/navigation"
import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts"

import { Button } from "@/components/ui/button"
import { StaffHeader } from "@/components/staff/staff-header"
import { Checkbox } from "@/components/ui/checkbox"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { StatusBadge } from "@/components/ui/status-badge"
import { Textarea } from "@/components/ui/textarea"
import {
  adminApi,
  type CategoryItem,
  type CrisisRuleItem,
  type GroupItem,
  type QuestionItem,
  type StaffCreateResult,
  type StaffItem,
  type Analytics,
  type AdminAppealItem,
} from "@/lib/admin"
import { ApiError } from "@/lib/api"
import { useAuth } from "@/lib/auth"

const sections = [
  ["overview", "Обзор"], ["appeals", "Обращения"],
  ["staff", "Сотрудники"],
  ["types", "Типы заявителей"], ["categories", "Категории"],
  ["questions", "Вопросы"], ["groups", "Группы специалистов"],
  ["routing", "Маршрутизация"], ["crisis", "Кризисные маркеры"],
  ["support", "Экстренная помощь"], ["audit", "Аудит"],
  ["settings", "Настройки"],
] as const
type Section = (typeof sections)[number][0]
type StaffRequest = ReturnType<typeof useAuth>["request"]
type Run = (action: () => Promise<unknown>, success?: string) => Promise<boolean>

function Panel({ title, note, children }: { title: string; note?: string; children: ReactNode }) {
  return <section className="staff-card space-y-5 p-6 sm:p-7">
    <div><h2 className="text-xl font-semibold tracking-tight">{title}</h2>{note ? <p className="mt-1 max-w-3xl text-[15px] leading-6 text-slate-500">{note}</p> : null}</div>{children}
  </section>
}

function CreatePanel({
  action,
  title,
  note,
  children,
}: {
  action: string
  title: string
  note?: string
  children: (close: () => void) => ReactNode
}) {
  const [open, setOpen] = useState(false)
  return <section className="staff-card p-6 sm:p-7"><div className="flex flex-wrap items-start justify-between gap-4"><div><h2 className="text-xl font-semibold tracking-tight">{title}</h2>{note ? <p className="mt-1 max-w-3xl text-[15px] leading-6 text-slate-500">{note}</p> : null}</div>{!open ? <Button type="button" size="lg" onClick={() => setOpen(true)}>{action}</Button> : null}</div>{open ? <div className="mt-6 border-t border-slate-100 pt-6">{children(() => setOpen(false))}</div> : null}</section>
}

function CreateActions({ busy, close }: { busy: boolean; close: () => void }) {
  return <div className="flex flex-col gap-2 sm:col-span-2 sm:flex-row"><Button type="submit" disabled={busy}>{busy ? "Сохраняем…" : "Создать"}</Button><Button type="button" variant="outline" disabled={busy} onClick={close}>Отмена</Button></div>
}

function Field({ label, name, type = "text", required = false }: { label: string; name: string; type?: string; required?: boolean }) {
  return <div className="space-y-1"><Label htmlFor={name}>{label}</Label><Input id={name} name={name} type={type} required={required} /></div>
}

function ToggleList<T extends { id: string; is_active: boolean }>({ items, label, toggle, edit, busy }: { items: T[]; label: (value: T) => string; toggle: (value: T) => Promise<unknown>; edit?: (value: T) => void; busy: boolean }) {
  return <Panel title="Текущая конфигурация">{items.length ? <div className="divide-y">{items.map((item) => <div key={item.id} className="flex flex-wrap items-center justify-between gap-4 py-4"><span className="text-base leading-6">{label(item)}</span><div className="flex flex-wrap gap-2">{edit ? <Button variant="outline" disabled={busy} onClick={() => edit(item)}>Изменить</Button> : null}<Button variant="outline" disabled={busy} onClick={() => { if (window.confirm("Изменить активность записи?")) void toggle(item) }}>{item.is_active ? "Деактивировать" : "Активировать"}</Button></div></div>)}</div> : <p className="text-base text-slate-500">Записей пока нет.</p>}</Panel>
}

export default function AdminWorkspacePage() {
  const router = useRouter(); const client = useQueryClient()
  const { staff: actor, status, request, logout } = useAuth()
  const [section, setSection] = useState<Section>("overview")
  const [rangeDays, setRangeDays] = useState(30)
  const [analyticsEnd] = useState(() => new Date())
  const [busy, setBusy] = useState(false); const [message, setMessage] = useState(""); const [error, setError] = useState("")
  const enabled = status === "authenticated" && actor?.role === "admin" && !actor.must_change_password
  useEffect(() => { if (status === "anonymous") router.replace("/staff/login"); else if (status === "authenticated" && actor?.must_change_password) router.replace("/staff/change-password"); else if (status === "authenticated" && actor?.role !== "admin") router.replace(`/staff/${actor?.role}`) }, [actor, router, status])

  const staff = useQuery({ queryKey: ["admin", "staff"], queryFn: () => adminApi.staff(request), enabled })
  const types = useQuery({ queryKey: ["admin", "types"], queryFn: () => adminApi.applicantTypes(request), enabled })
  const categories = useQuery({ queryKey: ["admin", "categories"], queryFn: () => adminApi.categories(request), enabled })
  const questions = useQuery({ queryKey: ["admin", "questions"], queryFn: () => adminApi.questions(request), enabled })
  const groups = useQuery({ queryKey: ["admin", "groups"], queryFn: () => adminApi.groups(request), enabled })
  const routing = useQuery({ queryKey: ["admin", "routing"], queryFn: () => adminApi.routing(request), enabled })
  const crisis = useQuery({ queryKey: ["admin", "crisis"], queryFn: () => adminApi.crisisRules(request), enabled })
  const support = useQuery({ queryKey: ["admin", "support"], queryFn: () => adminApi.supportResources(request), enabled })
  const settings = useQuery({ queryKey: ["admin", "settings"], queryFn: () => adminApi.settings(request), enabled })
  const appeals = useQuery({ queryKey: ["admin", "appeals"], queryFn: () => adminApi.appeals(request), enabled })
  const today = analyticsEnd.toISOString().slice(0, 10)
  const rangeStart = new Date(analyticsEnd.getTime() - (rangeDays - 1) * 86400000).toISOString().slice(0, 10)
  const analytics = useQuery({ queryKey: ["admin", "analytics", rangeDays], queryFn: () => adminApi.analytics(request, rangeStart, today), enabled })

  async function run(action: () => Promise<unknown>, success = "Изменения сохранены.") {
    setBusy(true); setError(""); setMessage("")
    try { const value = await action(); setMessage(value && typeof value === "object" && "message" in value ? String(value.message) : success); await client.invalidateQueries({ queryKey: ["admin"] }); return true }
    catch (caught) { setError(caught instanceof ApiError ? caught.message : "Не удалось выполнить действие. Проверьте данные и повторите попытку."); return false }
    finally { setBusy(false) }
  }
  if (!enabled) return <main className="p-6 text-sm text-slate-500">Проверяем права доступа…</main>
  const failed = [staff, types, categories, questions, groups, routing, crisis, support, settings, appeals, analytics].some((query) => query.isError)

  return <main className="staff-workspace"><StaffHeader title="Управление продуктом" role="Администратор" name={actor.display_name} onLogout={() => { void logout().finally(() => router.replace("/staff/login")) }} navigation={sections.map(([id, label]) => ({ id, label, active: section === id, onSelect: () => setSection(id) }))} />
    <div className="mx-auto w-full max-w-[1600px] p-4 sm:p-6 lg:p-8 xl:px-10"><div className="min-w-0 space-y-6">
      {failed ? <p className="state-error" role="alert">Часть данных не загрузилась.</p> : null}{message ? <p className="state-success" role="status">{message}</p> : null}{error ? <p className="state-error" role="alert">{error}</p> : null}
      {section === "overview" ? <Overview analytics={analytics.data} rangeDays={rangeDays} setRangeDays={setRangeDays} request={request} /> : null}
      {section === "staff" ? <StaffView items={staff.data ?? []} request={request} run={run} busy={busy} /> : null}
      {section === "appeals" ? <AppealsView items={appeals.data?.items ?? []} staff={staff.data ?? []} request={request} run={run} busy={busy} /> : null}
      {section === "audit" ? <AuditView staff={staff.data ?? []} request={request} /> : null}
      {section === "types" ? <TypesView items={types.data ?? []} request={request} run={run} busy={busy} /> : null}
      {section === "categories" ? <CategoriesView items={categories.data ?? []} questions={questions.data ?? []} request={request} run={run} busy={busy} /> : null}
      {section === "questions" ? <QuestionsView items={questions.data ?? []} request={request} run={run} busy={busy} /> : null}
      {section === "groups" ? <GroupsView items={groups.data ?? []} staff={staff.data ?? []} request={request} run={run} busy={busy} /> : null}
      {section === "routing" ? <RoutingView categories={categories.data ?? []} groups={groups.data ?? []} routes={routing.data ?? []} request={request} run={run} busy={busy} /> : null}
      {section === "crisis" ? <CrisisView items={crisis.data ?? []} request={request} run={run} busy={busy} /> : null}
      {section === "support" ? <SupportView items={support.data ?? []} request={request} run={run} busy={busy} /> : null}
      {section === "settings" ? <Panel title="Безопасные настройки" note="Секреты не доступны через API. Эти параметры пока читаются из окружения.">{settings.data?.settings.map((item) => <div key={item.key} className="flex justify-between border-b py-2 text-sm"><span>{item.key}</span><strong>{item.value}</strong></div>)}</Panel> : null}
    </div></div></main>
}

function Overview({ analytics, rangeDays, setRangeDays, request }: { analytics?: Analytics; rangeDays: number; setRangeDays: (value: number) => void; request: StaffRequest }) {
  const metrics = [["Всего обращений", analytics?.total], ["Срочных", analytics?.urgent_share == null ? null : `${Math.round(analytics.urgent_share * 100)}%`], ["Возвратов", analytics?.returned_share == null ? null : `${Math.round(analytics.returned_share * 100)}%`], ["До оператора", duration(analytics?.avg_operator_acceptance_seconds)], ["Первый ответ", duration(analytics?.avg_first_response_seconds)], ["Решение", duration(analytics?.avg_resolution_seconds)]]
  async function download() { if (!analytics) return; const blob = await adminApi.exportAnalytics(request, analytics.date_from, analytics.date_to); const url = URL.createObjectURL(blob); const link = document.createElement("a"); link.href = url; link.download = "otklik-appeals.csv"; link.click(); URL.revokeObjectURL(url) }
  return <><Panel title="Аналитика" note="Только операционные метаданные — без содержимого обращений."><div className="flex flex-wrap gap-3"><Button size="lg" variant={rangeDays === 7 ? "default" : "outline"} onClick={() => setRangeDays(7)}>7 дней</Button><Button size="lg" variant={rangeDays === 30 ? "default" : "outline"} onClick={() => setRangeDays(30)}>30 дней</Button><Button size="lg" variant="outline" disabled={!analytics} onClick={() => void download()}>Скачать CSV</Button></div><div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">{metrics.map(([name, value], index) => <div key={String(name)} className={`min-h-36 rounded-2xl border p-6 ${index === 0 ? "border-indigo-200 bg-indigo-50" : "border-slate-200 bg-slate-50"}`}><p className="text-[15px] font-medium text-slate-500">{name}</p><p className="mt-4 text-4xl font-semibold tracking-tight text-slate-950">{value ?? "—"}</p></div>)}</div></Panel>{analytics ? <><ChartPanel title="Обращения по дням" data={analytics.daily} kind="line" /><div className="grid gap-6 xl:grid-cols-2"><ChartPanel title="Категории" data={analytics.by_category} /><ChartPanel title="Статусы" data={analytics.by_status} /><ChartPanel title="Типы заявителей" data={analytics.by_applicant_type} /></div><Panel title="Нагрузка">{analytics.workloads.length ? analytics.workloads.map((item) => <div key={item.staff_user_id} className="flex justify-between gap-4 border-b border-slate-100 py-4 text-base"><span>{item.display_name} · {item.role}</span><strong className="shrink-0 rounded-full bg-slate-100 px-3 py-1.5">{item.active_appeals}{item.capacity == null ? " действий" : ` / ${item.capacity}`}</strong></div>) : <p className="text-base text-slate-500">Нет данных.</p>}</Panel></> : <Panel title="Аналитика"><p className="text-base text-slate-500">Загрузка…</p></Panel>}</>
}

function duration(seconds: number | null | undefined) { if (seconds == null) return null; if (seconds < 3600) return `${Math.round(seconds / 60)} мин`; return `${(seconds / 3600).toFixed(1)} ч` }

function ChartPanel({ title, data, kind = "bar" }: { title: string; data: Array<{ key?: string; date?: string; count: number }>; kind?: "bar" | "line" }) {
  return <Panel title={title}>{data.length ? <div className="h-80 min-w-0 sm:h-88"><ResponsiveContainer width="100%" height="100%">{kind === "line" ? <LineChart data={data}><CartesianGrid stroke="#e2e8f0" strokeDasharray="3 3" vertical={false} /><XAxis dataKey="date" tick={{ fill: "#64748b", fontSize: 13 }} /><YAxis allowDecimals={false} tick={{ fill: "#64748b", fontSize: 13 }} /><Tooltip /><Line dataKey="count" stroke="#4f46e5" strokeWidth={3} dot={false} /></LineChart> : <BarChart data={data}><CartesianGrid stroke="#e2e8f0" strokeDasharray="3 3" vertical={false} /><XAxis dataKey="key" hide /><YAxis allowDecimals={false} tick={{ fill: "#64748b", fontSize: 13 }} /><Tooltip /><Bar dataKey="count" fill="#6366f1" radius={[8, 8, 0, 0]} /></BarChart>}</ResponsiveContainer></div> : <p className="text-base text-slate-500">Нет данных за период.</p>}</Panel>
}

function AppealsView({ items, staff, request, run, busy }: { items: AdminAppealItem[]; staff: StaffItem[]; request: StaffRequest; run: Run; busy: boolean }) {
  const experts = staff.filter((item) => item.role === "expert" && item.is_active)
  const reason = () => window.prompt("Обязательная служебная причина (без содержимого обращения)")?.trim()
  return <Panel title="Зависшие обращения" note="Только метаданные. Содержимое, сообщения, заметки, вложения и контакты здесь недоступны.">{items.length ? <div className="space-y-3">{items.map((item) => <div key={item.id} className="rounded-xl border border-slate-200 p-4"><div className="flex flex-wrap justify-between gap-3"><div className="min-w-0"><p className="break-safe font-medium">{item.category_name ?? "Без категории"} · {item.applicant_type}</p><p className="break-safe mt-1 font-mono text-xs text-slate-500">{item.id}</p><div className="mt-2 flex flex-wrap gap-1.5"><StatusBadge value={item.status} /><StatusBadge value={item.priority} />{item.crisis_flag ? <StatusBadge value="crisis" /> : null}</div><p className="mt-2 text-sm">Специалист: {item.assigned_expert_display_name ?? "не назначен"}</p></div></div><div className="mt-3 flex flex-wrap gap-2"><Button size="sm" variant="outline" disabled={busy} onClick={() => { const status = window.prompt("Статус: new, assigned, in_progress, needs_clarification или returned", item.status); const why = reason(); if (status && why) void run(() => adminApi.interveneAppeal(request, item.id, { status, reason: why })) }}>Статус</Button><Button size="sm" variant="outline" disabled={busy} onClick={() => { const priority = window.prompt("Приоритет: low, standard или urgent", item.priority); const why = reason(); if (priority && why) void run(() => adminApi.interveneAppeal(request, item.id, { priority, reason: why })) }}>Приоритет</Button><Button size="sm" variant="outline" disabled={busy} onClick={() => { const expert = window.prompt(`UUID специалиста (пусто — снять назначение):\n${experts.map((value) => `${value.display_name}: ${value.id}`).join("\n")}`, item.assigned_expert_id ?? ""); if (expert === null) return; const why = reason(); if (why) void run(() => adminApi.interveneAppeal(request, item.id, { assigned_expert_id: expert || null, status: expert ? "assigned" : "new", reason: why })) }}>Назначение</Button></div></div>)}</div> : <p className="text-sm text-slate-500">Обращений пока нет.</p>}</Panel>
}

function AuditView({ staff, request }: { staff: StaffItem[]; request: StaffRequest }) {
  const [page, setPage] = useState(1); const [action, setAction] = useState(""); const [actor, setActor] = useState(""); const [entity, setEntity] = useState("")
  const [from, setFrom] = useState(""); const [to, setTo] = useState(""); const params = new URLSearchParams({ page: String(page), page_size: "50" }); if (action) params.set("action", action); if (actor) params.set("actor_id", actor); if (entity) params.set("entity_type", entity); if (from) params.set("date_from", `${from}T00:00:00Z`); if (to) params.set("date_to", `${to}T23:59:59Z`)
  const audit = useQuery({ queryKey: ["admin", "audit", page, action, actor, entity, from, to], queryFn: () => adminApi.audit(request, `?${params}`) })
  return <Panel title="Аудит" note="Только безопасные операционные события; расшифровка содержимого не выполняется."><div className="grid gap-2 sm:grid-cols-3"><Input placeholder="Действие" value={action} onChange={(event) => { setAction(event.target.value); setPage(1) }} /><select className="h-10 rounded-md border px-3" value={actor} onChange={(event) => { setActor(event.target.value); setPage(1) }}><option value="">Все сотрудники</option>{staff.map((item) => <option key={item.id} value={item.id}>{item.display_name}</option>)}</select><Input placeholder="Тип сущности" value={entity} onChange={(event) => { setEntity(event.target.value); setPage(1) }} /><Input type="date" value={from} onChange={(event) => { setFrom(event.target.value); setPage(1) }} /><Input type="date" value={to} onChange={(event) => { setTo(event.target.value); setPage(1) }} /></div>{audit.isError ? <p className="text-sm text-rose-700">Не удалось загрузить аудит.</p> : audit.data?.items.map((item) => <div key={item.id} className="border-b py-3 text-sm"><div className="flex flex-wrap justify-between gap-2"><strong>{item.action}</strong><span>{new Date(item.created_at).toLocaleString("ru-RU")}</span></div><p>{item.actor_display_name ?? "Система"} · {item.entity_type} · {item.entity_id ?? "—"}</p>{item.reason ? <p className="mt-1 text-slate-600">Причина: {item.reason}</p> : null}<code className="text-xs text-slate-500">{JSON.stringify(item.metadata ?? {})}</code></div>)}<div className="flex gap-2"><Button variant="outline" disabled={page === 1} onClick={() => setPage((value) => value - 1)}>Назад</Button><Button variant="outline" disabled={!audit.data || page * 50 >= audit.data.total} onClick={() => setPage((value) => value + 1)}>Далее</Button></div></Panel>
}

function StaffView({ items, request, run, busy }: { items: StaffItem[]; request: StaffRequest; run: Run; busy: boolean }) {
  const [newRole, setNewRole] = useState<"operator" | "expert" | "admin">("operator")
  const [credentials, setCredentials] = useState<StaffCreateResult | null>(null)
  async function copyCredentials() {
    if (!credentials) return
    await navigator.clipboard.writeText(`Логин: ${credentials.staff.login}\nВременный пароль: ${credentials.temporary_password}`)
  }
  return <><CreatePanel action="Добавить сотрудника" title="Сотрудники" note="После создания временный пароль будет показан один раз.">{(close) => <form className="grid gap-3 sm:grid-cols-2" onSubmit={(event) => { event.preventDefault(); const form = event.currentTarget; const f = new FormData(form); const expert = newRole === "expert"; let created: StaffCreateResult | null = null; void run(async () => { created = await adminApi.createStaff(request, { login: f.get("login"), email: f.get("email"), display_name: f.get("name"), role: newRole, ...(expert ? { public_specialist_label: f.get("label"), max_active_appeals: Number(f.get("capacity") || 10) } : {}) }); return created }, "Сотрудник создан.").then((saved) => { if (saved && created) { setCredentials(created); form.reset(); setNewRole("operator"); close() } }) }}><Field label="Логин" name="login" required /><Field label="Email" name="email" type="email" required /><Field label="Отображаемое имя" name="name" required /><div><Label htmlFor="role">Роль</Label><select id="role" name="role" value={newRole} onChange={(event) => setNewRole(event.target.value as typeof newRole)} className="h-10 w-full rounded-md border px-3"><option value="operator">Оператор</option><option value="expert">Эксперт</option><option value="admin">Администратор</option></select></div>{newRole === "expert" ? <><Field label="Специализация эксперта" name="label" required /><Field label="Вместимость" name="capacity" type="number" required /></> : null}<CreateActions busy={busy} close={() => { setNewRole("operator"); close() }} /></form>}</CreatePanel>
    {credentials ? <div className="fixed inset-0 z-50 grid place-items-center overflow-y-auto bg-slate-950/45 p-4" role="dialog" aria-modal="true" aria-labelledby="credentials-title"><div className="my-auto max-h-[calc(100vh-2rem)] w-full max-w-2xl overflow-y-auto rounded-2xl border border-slate-200 bg-white p-6 shadow-2xl sm:p-10"><div className="mb-6 flex size-12 items-center justify-center rounded-full bg-indigo-100 text-2xl text-indigo-800">✓</div><h2 id="credentials-title" className="text-3xl font-semibold tracking-tight">Сотрудник создан</h2><p className="mt-3 text-base leading-7 text-slate-600">Сохраните данные сейчас. Временный пароль больше не будет показан.</p><div className="my-7 space-y-3 rounded-2xl border border-indigo-100 bg-indigo-50/60 p-5 sm:p-6"><p className="text-sm font-medium text-slate-500">Логин</p><p className="break-safe font-mono text-xl font-semibold">{credentials.staff.login}</p><p className="pt-3 text-sm font-medium text-slate-500">Временный пароль</p><p className="break-safe font-mono text-xl font-semibold">{credentials.temporary_password}</p></div><div className="grid gap-3 sm:grid-cols-2"><Button type="button" size="lg" onClick={() => void copyCredentials()}>Копировать данные</Button><Button type="button" size="lg" variant="outline" onClick={() => setCredentials(null)}>Готово</Button></div></div></div> : null}
    <Panel title="Сотрудники">{items.map((item) => <div key={item.id} className="mb-4 rounded-2xl border p-5"><div className="flex flex-wrap justify-between gap-4"><div><p className="text-lg font-semibold">{item.display_name}</p><p className="mt-1 text-[15px] text-slate-500">{item.login} · {item.email} · {item.role}</p>{item.role === "expert" ? <p className="mt-2 text-base">{item.public_specialist_label || "Специалист"}: {item.active_appeals}/{item.max_active_appeals}</p> : null}</div><span className="text-sm font-medium text-slate-600">{item.is_active ? "Активен" : "Отключён"}</span></div><div className="mt-4 flex flex-wrap gap-2"><Button variant="outline" onClick={() => { const display_name = window.prompt("Отображаемое имя", item.display_name); const email = window.prompt("Email", item.email ?? ""); if (display_name && email) void run(() => adminApi.updateStaff(request, item.id, { display_name, email })) }}>Профиль</Button><Button variant="outline" onClick={() => { const role = window.prompt("Роль: operator, expert или admin", item.role); if (role === "expert") { const label = window.prompt("Публичная специализация", item.public_specialist_label ?? ""); const capacity = window.prompt("Максимум активных обращений", String(item.max_active_appeals ?? 10)); if (label && capacity) void run(() => adminApi.updateStaff(request, item.id, { role, public_specialist_label: label, max_active_appeals: Number(capacity) })) } else if (role === "operator" || role === "admin") void run(() => adminApi.updateStaff(request, item.id, { role })) }}>Роль</Button><Button variant="outline" onClick={() => { if (window.confirm("Изменить состояние сотрудника и отозвать сессии?")) void run(() => adminApi.updateStaff(request, item.id, { is_active: !item.is_active })) }}>{item.is_active ? "Деактивировать" : "Активировать"}</Button>{item.role === "expert" ? <><Button variant="outline" onClick={() => { const value = window.prompt("Публичная специализация", item.public_specialist_label ?? ""); if (value) void run(() => adminApi.updateStaff(request, item.id, { public_specialist_label: value })) }}>Специализация</Button><Button variant="outline" onClick={() => { const value = window.prompt("Максимум активных обращений", String(item.max_active_appeals)); if (value) void run(() => adminApi.updateStaff(request, item.id, { max_active_appeals: Number(value) })) }}>Изменить лимит</Button></> : null}</div></div>)}</Panel></>
}

function TypesView({ items, request, run, busy }: { items: Array<{ id: string; code: string; label: string; description: string | null; tone: string; is_active: boolean; sort_order: number }>; request: StaffRequest; run: Run; busy: boolean }) {
  return <><CreatePanel action="Добавить тип заявителя" title="Кто обращается" note="Активные варианты сразу появляются в публичной форме.">{(close) => <form className="grid gap-3 sm:grid-cols-2" onSubmit={(event) => { event.preventDefault(); const form = event.currentTarget; const f = new FormData(form); void run(() => adminApi.createApplicantType(request, { code: f.get("code"), label: f.get("label"), description: f.get("description") || null, tone: f.get("tone"), is_active: f.get("active") === "on", sort_order: Number(f.get("order") || 0) })).then((saved) => { if (saved) { form.reset(); close() } }) }}><Field label="Код" name="code" required /><Field label="Название" name="label" required /><Field label="Описание" name="description" /><Field label="Порядок" name="order" type="number" /><select name="tone" className="h-10 rounded-md border px-3"><option value="informal">Обращение на «ты»</option><option value="formal">Обращение на «вы»</option></select><label className="flex items-center gap-2"><input type="checkbox" name="active" defaultChecked />Активен</label><CreateActions busy={busy} close={close} /></form>}</CreatePanel><ToggleList items={items} label={(x) => `${x.label} · ${x.tone === "informal" ? "ты" : "вы"} · ${x.sort_order}`} edit={(x) => { const label = window.prompt("Название", x.label); const description = window.prompt("Описание", x.description ?? ""); const tone = window.prompt("Тон: informal или formal", x.tone); const order = window.prompt("Порядок", String(x.sort_order)); if (label && description !== null && order && (tone === "informal" || tone === "formal")) void run(() => adminApi.updateApplicantType(request, x.id, { label, description: description || null, tone, sort_order: Number(order) })) }} toggle={(x) => run(() => adminApi.updateApplicantType(request, x.id, { is_active: !x.is_active }))} busy={busy} /></>
}

function CategoriesView({ items, questions, request, run, busy }: { items: CategoryItem[]; questions: QuestionItem[]; request: StaffRequest; run: Run; busy: boolean }) {
  const [category, setCategory] = useState(""); const mapped = questions.filter((q) => q.category_ids.includes(category)).map((q) => q.id); const [draft, setDraft] = useState<string[] | null>(null); const selected = draft ?? mapped
  return <><CreatePanel action="Добавить категорию" title="Категории">{(close) => <form className="grid gap-3 sm:grid-cols-2" onSubmit={(event) => { event.preventDefault(); const form = event.currentTarget; const f = new FormData(form); void run(() => adminApi.createCategory(request, { slug: f.get("slug"), name: f.get("name"), description: f.get("description") || null, is_active: f.get("active") === "on", sort_order: Number(f.get("order") || 0) })).then((saved) => { if (saved) { form.reset(); close() } }) }}><Field label="Slug" name="slug" required /><Field label="Название" name="name" required /><Field label="Подсказка" name="description" /><Field label="Порядок" name="order" type="number" /><label className="flex items-center gap-2"><input type="checkbox" name="active" defaultChecked />Активна</label><CreateActions busy={busy} close={close} /></form>}</CreatePanel><ToggleList items={items} label={(x) => `${x.name} · ${x.sort_order}`} edit={(x) => { const name = window.prompt("Название", x.name); const description = window.prompt("Подсказка", x.description ?? ""); const order = window.prompt("Порядок", String(x.sort_order)); if (name && order) void run(() => adminApi.updateCategory(request, x.id, { name, description: description || null, sort_order: Number(order) })) }} toggle={(x) => run(() => adminApi.updateCategory(request, x.id, { is_active: !x.is_active }))} busy={busy} /><Panel title="Вопросы категории"><select value={category} onChange={(e) => { setCategory(e.target.value); setDraft(null) }} className="h-10 w-full rounded-md border px-3"><option value="">Выберите категорию</option>{items.map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}</select>{category ? <div className="space-y-2">{questions.map((q) => <label key={q.id} className="flex gap-2"><Checkbox checked={selected.includes(q.id)} onCheckedChange={(checked) => setDraft(checked ? [...selected, q.id] : selected.filter((id) => id !== q.id))} />{q.label}</label>)}<Button disabled={busy} onClick={() => void run(() => adminApi.setCategoryQuestions(request, category, selected.map((question_id, index) => ({ question_id, sort_order: (index + 1) * 10 }))))}>Сохранить</Button></div> : null}</Panel></>
}

function QuestionsView({ items, request, run, busy }: { items: QuestionItem[]; request: StaffRequest; run: Run; busy: boolean }) {
  const [newType, setNewType] = useState("short_text")
  return <><CreatePanel action="Добавить вопрос" title="Динамические вопросы" note="Для вопросов с выбором перечислите варианты через запятую.">{(close) => <form className="grid gap-3 sm:grid-cols-2" onSubmit={(event) => { event.preventDefault(); const form = event.currentTarget; const f = new FormData(form); const options = String(f.get("options") || "").split(",").map((x) => x.trim()).filter(Boolean); void run(() => adminApi.createQuestion(request, { code: f.get("code"), label: f.get("label"), help_text: f.get("help") || null, field_type: newType, options: newType.includes("choice") ? options : [], required: f.get("required") === "on", is_active: f.get("active") === "on", sort_order: Number(f.get("order") || 0) })).then((saved) => { if (saved) { form.reset(); setNewType("short_text"); close() } }) }}><Field label="Код" name="code" required /><Field label="Текст" name="label" required /><Field label="Подсказка" name="help" /><select name="type" value={newType} onChange={(event) => setNewType(event.target.value)} className="h-10 rounded-md border px-3"><option value="short_text">Короткий текст</option><option value="long_text">Длинный текст</option><option value="single_choice">Один вариант</option><option value="multi_choice">Несколько вариантов</option><option value="boolean">Да/нет</option></select>{newType.includes("choice") ? <Field label="Варианты" name="options" required /> : null}<Field label="Порядок" name="order" type="number" /><label className="flex items-center gap-2"><input type="checkbox" name="required" />Обязательный</label><label className="flex items-center gap-2"><input type="checkbox" name="active" defaultChecked />Активен</label><CreateActions busy={busy} close={() => { setNewType("short_text"); close() }} /></form>}</CreatePanel><ToggleList items={items} label={(x) => `${x.label} · ${x.field_type} · ${x.sort_order}`} edit={(x) => { const label = window.prompt("Текст вопроса", x.label); const help = window.prompt("Подсказка", x.help_text ?? ""); const type = window.prompt("Тип: short_text, long_text, single_choice, multi_choice или boolean", x.field_type); const options = window.prompt("Варианты через запятую", x.options.join(", ")); const required = window.prompt("Обязательный: true или false", String(x.required)); const order = window.prompt("Порядок", String(x.sort_order)); if (label && help !== null && type && options !== null && order && (required === "true" || required === "false")) void run(() => adminApi.updateQuestion(request, x.id, { label, help_text: help || null, field_type: type, options: type.includes("choice") ? options.split(",").map((value) => value.trim()).filter(Boolean) : [], required: required === "true", sort_order: Number(order) })) }} toggle={(x) => run(() => adminApi.updateQuestion(request, x.id, { is_active: !x.is_active }))} busy={busy} /></>
}

function GroupsView({ items, staff, request, run, busy }: { items: GroupItem[]; staff: StaffItem[]; request: StaffRequest; run: Run; busy: boolean }) {
  const experts = staff.filter((x) => x.role === "expert")
  return <><CreatePanel action="Добавить группу" title="Группы специалистов">{(close) => <form className="grid gap-3 sm:grid-cols-2" onSubmit={(event) => { event.preventDefault(); const form = event.currentTarget; const f = new FormData(form); void run(() => adminApi.createGroup(request, { slug: f.get("slug"), name: f.get("name"), description: f.get("description") || null, is_active: f.get("active") === "on" })).then((saved) => { if (saved) { form.reset(); close() } }) }}><Field label="Slug" name="slug" required /><Field label="Название" name="name" required /><Field label="Описание" name="description" /><label className="flex items-center gap-2"><input type="checkbox" name="active" defaultChecked />Активна</label><CreateActions busy={busy} close={close} /></form>}</CreatePanel>{items.map((group) => <Panel key={group.id} title={group.name} note={`${group.active_experts} активных, ${group.available_experts} доступных, нагрузка ${group.active_load}/${group.total_capacity}`}><div className="grid gap-2">{experts.map((expert) => <label key={expert.id} className="flex gap-2"><Checkbox checked={group.member_ids.includes(expert.id)} onCheckedChange={(checked) => void run(() => adminApi.setMembers(request, group.id, checked ? [...group.member_ids, expert.id] : group.member_ids.filter((id) => id !== expert.id)))} />{expert.display_name} · {expert.public_specialist_label || expert.login}</label>)}</div><div className="flex gap-2"><Button variant="outline" size="sm" onClick={() => { const name = window.prompt("Название", group.name); const description = window.prompt("Описание", group.description ?? ""); if (name) void run(() => adminApi.updateGroup(request, group.id, { name, description: description || null })) }}>Изменить</Button><Button variant="outline" size="sm" onClick={() => { if (window.confirm("Изменить активность группы?")) void run(() => adminApi.updateGroup(request, group.id, { is_active: !group.is_active })) }}>{group.is_active ? "Деактивировать" : "Активировать"}</Button></div></Panel>)}</>
}

function RoutingView({ categories, groups, routes, request, run, busy }: { categories: CategoryItem[]; groups: GroupItem[]; routes: Array<{ category_id: string; group_ids: string[] }>; request: StaffRequest; run: Run; busy: boolean }) {
  return <Panel title="Маршрутизация" note="Изменения сразу используются серверной рекомендацией.">{categories.map((category) => { const selected = routes.find((x) => x.category_id === category.id)?.group_ids ?? []; return <div key={category.id} className="mb-4 rounded-xl border p-4"><p className="font-medium">{category.name}</p><div className="mt-2 grid gap-2 sm:grid-cols-2">{groups.map((group) => <label key={group.id} className="flex gap-2 text-sm"><Checkbox disabled={busy} checked={selected.includes(group.id)} onCheckedChange={(checked) => void run(() => adminApi.setRouting(request, category.id, checked ? [...selected, group.id] : selected.filter((id) => id !== group.id)))} />{group.name} · {group.available_experts}/{group.active_experts} доступно</label>)}</div></div>})}</Panel>
}

function CrisisView({ items, request, run, busy }: { items: CrisisRuleItem[]; request: StaffRequest; run: Run; busy: boolean }) {
  const [text, setText] = useState(""); const [result, setResult] = useState("")
  return <><CreatePanel action="Добавить правило" title="Кризисные маркеры" note="Только буквальное нормализованное сопоставление — без regex и fuzzy matching.">{(close) => <form className="grid gap-3 sm:grid-cols-2" onSubmit={(event) => { event.preventDefault(); const form = event.currentTarget; const f = new FormData(form); void run(() => adminApi.createCrisisRule(request, { phrase: f.get("phrase"), is_active: f.get("active") === "on", allow_compact_match: f.get("compact") === "on", sort_order: Number(f.get("order") || 0) })).then((saved) => { if (saved) { form.reset(); close() } }) }}><Field label="Фраза" name="phrase" required /><Field label="Порядок" name="order" type="number" /><label className="flex items-center gap-2"><input name="compact" type="checkbox" />Слитное написание</label><label className="flex items-center gap-2"><input name="active" type="checkbox" defaultChecked />Активно</label><CreateActions busy={busy} close={close} /></form>}</CreatePanel><ToggleList items={items} label={(x) => `${x.phrase}${x.allow_compact_match ? " · слитно" : ""} · ${x.sort_order}`} edit={(x) => { const phrase = window.prompt("Фраза", x.phrase); const compact = window.prompt("Слитное сопоставление: true или false", String(x.allow_compact_match)); const order = window.prompt("Порядок", String(x.sort_order)); if (phrase && order && (compact === "true" || compact === "false")) void run(() => adminApi.updateCrisisRule(request, x.id, { phrase, allow_compact_match: compact === "true", sort_order: Number(order) })) }} toggle={(x) => run(() => adminApi.updateCrisisRule(request, x.id, { is_active: !x.is_active }))} busy={busy} /><Panel title="Проверить фразу" note="Текст проверки не сохраняется и не аудируется."><Textarea value={text} onChange={(e) => setText(e.target.value)} /><Button disabled={!text || busy} onClick={() => void adminApi.testCrisisRule(request, text).then((value) => setResult(value.crisis_detected ? `Сработает: ${value.matched_rules.map((x) => x.phrase).join(", ")}` : "Не сработает")).catch(() => setResult("Не удалось проверить фразу"))}>Проверить</Button>{result ? <p className="font-medium">{result}</p> : null}</Panel></>
}

function SupportView({ items, request, run, busy }: { items: Array<{ id: string; title: string; description: string; phone: string | null; url: string | null; region: string | null; is_active: boolean; sort_order: number }>; request: StaffRequest; run: Run; busy: boolean }) {
  return <><CreatePanel action="Добавить ресурс" title="Экстренная помощь" note="Добавляйте только согласованные организаторами ресурсы.">{(close) => <form className="grid gap-3 sm:grid-cols-2" onSubmit={(event) => { event.preventDefault(); const form = event.currentTarget; const f = new FormData(form); void run(() => adminApi.createSupportResource(request, { title: f.get("title"), description: f.get("description"), phone: f.get("phone") || null, url: f.get("url") || null, region: f.get("region") || null, is_active: f.get("active") === "on", sort_order: Number(f.get("order") || 0) })).then((saved) => { if (saved) { form.reset(); close() } }) }}><Field label="Название" name="title" required /><Field label="Регион" name="region" /><div className="sm:col-span-2"><Label htmlFor="description">Описание</Label><Textarea id="description" name="description" required /></div><Field label="Телефон" name="phone" /><Field label="URL" name="url" /><Field label="Порядок" name="order" type="number" /><label className="flex items-center gap-2"><input type="checkbox" name="active" defaultChecked />Активен</label><CreateActions busy={busy} close={close} /></form>}</CreatePanel><ToggleList items={items} label={(x) => `${x.title} · ${x.phone || x.url} · ${x.sort_order}`} edit={(x) => { const title = window.prompt("Название", x.title); const description = window.prompt("Описание", x.description); const phone = window.prompt("Телефон", x.phone ?? ""); const url = window.prompt("URL", x.url ?? ""); const region = window.prompt("Регион", x.region ?? ""); const order = window.prompt("Порядок", String(x.sort_order)); if (title && description && order && (phone || url)) void run(() => adminApi.updateSupportResource(request, x.id, { title, description, phone: phone || null, url: url || null, region: region || null, sort_order: Number(order) })) }} toggle={(x) => run(() => adminApi.updateSupportResource(request, x.id, { is_active: !x.is_active }))} busy={busy} /></>
}
