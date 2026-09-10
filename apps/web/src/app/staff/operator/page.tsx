"use client"

import { useCallback, useEffect, useMemo, useState } from "react"
import { useRouter } from "next/navigation"

import { Button } from "@/components/ui/button"
import { StaffHeader } from "@/components/staff/staff-header"
import { StatusBadge } from "@/components/ui/status-badge"
import { Textarea } from "@/components/ui/textarea"
import { useAuth } from "@/lib/auth"
import {
  type AppealPriority,
  type OperatorAppealDetail,
  type OperatorQueue,
  type OperatorReference,
  type OperatorTransferRequest,
  operatorApi,
} from "@/lib/operator"

const priorities: Record<AppealPriority, string> = {
  low: "Низкий",
  standard: "Обычный",
  urgent: "Срочный",
}

const applicantTypes: Record<string, string> = {
  student: "Ученик",
  parent: "Родитель",
  teacher: "Педагог",
} as const

function renderAnswer(value: string | boolean | string[]) {
  if (Array.isArray(value)) return value.join(", ")
  if (typeof value === "boolean") return value ? "Да" : "Нет"
  return value
}

const statuses: Record<string, string> = {
  new: "Новое",
  assigned: "Назначено",
  returned: "Возвращено",
  rejected: "Отклонено",
}

const intakeLabels: Record<string, string> = {
  where: "Где это происходит?",
  duration: "Как давно это происходит?",
  involved: "Кто участвует?",
  help_requested: "Обращались ли уже за помощью?",
}

function waiting(seconds: number) {
  const hours = Math.floor(seconds / 3600)
  if (hours < 1) return `${Math.max(1, Math.floor(seconds / 60))} мин.`
  return hours < 24 ? `${hours} ч.` : `${Math.floor(hours / 24)} дн.`
}

export default function OperatorWorkspacePage() {
  const router = useRouter()
  const { staff, status, request, logout } = useAuth()
  const [queue, setQueue] = useState<OperatorQueue | null>(null)
  const [reference, setReference] = useState<OperatorReference | null>(null)
  const [detail, setDetail] = useState<OperatorAppealDetail | null>(null)
  const [statusFilter, setStatusFilter] = useState("")
  const [priorityFilter, setPriorityFilter] = useState("")
  const [crisisOnly, setCrisisOnly] = useState(false)
  const [rejectReason, setRejectReason] = useState("")
  const [rejectKind, setRejectKind] = useState<"spam" | "outside_competence">("spam")
  const [selectedExpertId, setSelectedExpertId] = useState("")
  const [crisisContact, setCrisisContact] = useState<string | null>(null)
  const [transfers, setTransfers] = useState<OperatorTransferRequest[]>([])
  const [transferTargets, setTransferTargets] = useState<Record<string, string>>({})
  const [complaints, setComplaints] = useState<Array<{ id: string; body: string }>>([])
  const [error, setError] = useState("")
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    if (status === "anonymous") router.replace("/staff/login")
    if (status === "authenticated" && staff?.must_change_password) {
      router.replace("/staff/change-password")
    } else if (status === "authenticated" && staff?.role !== "operator") {
      router.replace(`/staff/${staff?.role}`)
    }
  }, [router, staff, status])

  const query = useMemo(() => {
    const params = new URLSearchParams()
    if (statusFilter) params.set("status", statusFilter)
    if (priorityFilter) params.set("priority", priorityFilter)
    if (crisisOnly) params.set("crisis", "true")
    return params.size ? `?${params}` : ""
  }, [crisisOnly, priorityFilter, statusFilter])

  const loadQueue = useCallback(async () => {
    setQueue(await operatorApi.queue(request, query))
  }, [query, request])

  const loadDetail = useCallback(
    async (id: string) => {
      setError("")
      setCrisisContact(null)
      setComplaints([])
      try {
        const loaded = await operatorApi.detail(request, id)
        setDetail(loaded)
        setSelectedExpertId(loaded.routing.recommended_expert?.expert_id ?? "")
      } catch {
        setError("Не удалось открыть обращение.")
      }
    },
    [request]
  )

  useEffect(() => {
    if (status !== "authenticated" || staff?.role !== "operator" || staff.must_change_password) return
    const timer = window.setTimeout(() => {
      void Promise.all([
        loadQueue(),
        operatorApi.reference(request).then(setReference),
        operatorApi.transferRequests(request).then(setTransfers),
      ]).catch(() => setError("Не удалось загрузить очередь оператора."))
    }, 0)
    return () => window.clearTimeout(timer)
  }, [loadQueue, request, staff, status])

  async function mutate(action: () => Promise<unknown>) {
    if (!detail) return
    setBusy(true)
    setError("")
    try {
      await action()
      await loadQueue()
      await loadDetail(detail.id)
      setTransfers(await operatorApi.transferRequests(request))
    } catch {
      setError("Действие не выполнено. Проверьте состояние обращения и выбранные данные.")
    } finally {
      setBusy(false)
    }
  }

  async function openAttachment(id: string) {
    if (!detail) return
    try {
      const blob = await operatorApi.attachment(request, detail.id, id)
      const url = URL.createObjectURL(blob)
      window.open(url, "_blank", "noopener,noreferrer")
      window.setTimeout(() => URL.revokeObjectURL(url), 60_000)
    } catch {
      setError("Не удалось открыть вложение.")
    }
  }

  if (status === "checking") {
    return <main className="m-auto p-6 text-sm text-slate-500">Проверяем сессию…</main>
  }
  if (status !== "authenticated" || staff?.role !== "operator") return null

  const crisisItems = queue?.items.filter((item) => item.crisis_flag) ?? []
  const regularItems = queue?.items.filter((item) => !item.crisis_flag) ?? []

  return (
    <main className="staff-workspace">
      <StaffHeader title="Очередь обращений" role="Оператор" name={staff.display_name} onLogout={() => { void logout().finally(() => router.replace("/staff/login")) }} />

      <div className="mx-auto grid w-full max-w-[1600px] gap-6 p-4 sm:p-6 lg:p-8 xl:grid-cols-[minmax(340px,0.32fr)_minmax(0,0.68fr)] xl:px-10">
        <aside className="space-y-4">
          {transfers.length ? <section className="space-y-2 rounded-xl bg-indigo-50 p-3 ring-1 ring-indigo-200"><h2 className="text-sm font-semibold">Запросы на передачу</h2>{transfers.map((item) => { const selected = transferTargets[item.id] ?? item.target_expert_id ?? ""; return <div key={item.id} className="rounded-lg bg-white p-3 text-sm"><p className="font-medium">{item.request_kind === "cannot_take" ? "Не может взять обращение" : "Передача другому специалисту"}</p><p className="mt-1"><span className="font-medium">{item.requester_display_name}</span>{item.target_display_name ? ` → ${item.target_display_name}` : " — оператор выбирает замену"}</p><p className="mt-1 text-slate-600">{item.reason}</p><select aria-label="Эксперт на замену" className="mt-2 w-full rounded-lg border p-2" value={selected} onChange={(event) => setTransferTargets((current) => ({ ...current, [item.id]: event.target.value }))}><option value="">Выберите подходящего эксперта</option>{item.eligible_experts.map((candidate) => <option key={candidate.expert_id} value={candidate.expert_id} disabled={!candidate.available}>{candidate.display_name} — {candidate.current_load}/{candidate.capacity}</option>)}</select><div className="mt-2 flex gap-2"><Button size="sm" disabled={busy || !selected} onClick={() => void operatorApi.resolveTransfer(request, item.id, "approve", selected).then(async () => { setTransfers(await operatorApi.transferRequests(request)); await loadQueue() }).catch(() => setError("Не удалось подтвердить передачу."))}>Подтвердить</Button><Button size="sm" variant="outline" disabled={busy} onClick={() => void operatorApi.resolveTransfer(request, item.id, "reject").then(async () => setTransfers(await operatorApi.transferRequests(request))).catch(() => setError("Не удалось отклонить передачу."))}>Отклонить</Button></div></div> })}</section> : null}
          <div className="grid grid-cols-2 gap-2">
            {queue ? ([
              ["Требуют внимания", queue.counters.crisis, "bg-amber-50"],
              ["Новые", queue.counters.new, "bg-white"],
              ["Возвращённые", queue.counters.returned, "bg-white"],
              ["Просроченные", queue.counters.overdue, "bg-white"],
            ] as const).map(([label, value, style]) => (
              <div key={label} className={`rounded-2xl border border-slate-200 p-4 shadow-sm ${style}`}><p className="text-3xl font-semibold tracking-tight">{value}</p><p className="mt-1 text-sm leading-5 text-slate-600">{label}</p></div>
            )) : null}
          </div>
          <div className="staff-card grid grid-cols-2 gap-3 p-4">
            <select aria-label="Статус" value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)} className="rounded-xl border p-3 text-sm">
              <option value="">Новые и возвращённые</option><option value="new">Новые</option><option value="returned">Возвращённые</option>
            </select>
            <select aria-label="Приоритет" value={priorityFilter} onChange={(event) => setPriorityFilter(event.target.value)} className="rounded-xl border p-3 text-sm">
              <option value="">Все приоритеты</option><option value="urgent">Срочный</option><option value="standard">Обычный</option><option value="low">Низкий</option>
            </select>
            <label className="col-span-2 flex items-center gap-2 text-sm"><input type="checkbox" checked={crisisOnly} onChange={(event) => setCrisisOnly(event.target.checked)} /> Только требующие внимания</label>
          </div>
          <QueueBlock title="Требуют внимания" items={crisisItems} selectedId={detail?.id} onOpen={loadDetail} />
          <QueueBlock title="Очередь" items={regularItems} selectedId={detail?.id} onOpen={loadDetail} />
        </aside>

        <section className="min-w-0">
          {error ? <p className="state-error mb-4" role="alert">{error}</p> : null}
          {!detail ? <div className="staff-card p-12 text-center text-base text-slate-500">Выберите обращение в очереди.</div> : (
            <div className="grid gap-6 2xl:grid-cols-[minmax(0,1fr)_minmax(320px,0.38fr)]">
              <div className="space-y-6">
                <section className="staff-card p-6 sm:p-8">
                  <div className="flex flex-wrap items-center gap-2 text-sm"><span className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1.5 font-medium text-slate-700">{applicantTypes[detail.applicant_type] ?? detail.applicant_type}</span><StatusBadge value={detail.status} label={statuses[detail.status] ?? detail.status} /><span className="text-slate-500">Ожидает {waiting(detail.waiting_seconds)}</span>{detail.crisis_flag ? <StatusBadge value="crisis" label="Требует внимания" /> : null}</div>
                  <h2 className="mt-6 text-xl font-semibold">Описание ситуации</h2><p className="mt-4 whitespace-pre-wrap text-[17px] leading-8 text-slate-800">{detail.description || "Описание не добавлено."}</p>
                </section>
                {Object.keys(detail.intake_answers).length ? <section className="staff-card p-6"><h2 className="text-lg font-semibold">Дополнительные ответы</h2><dl className="mt-5 space-y-4">{Object.entries(detail.intake_answers).map(([key, value]) => <div key={key}><dt className="text-sm text-slate-500">{intakeLabels[key] ?? key}</dt><dd className="mt-1 text-base leading-7">{renderAnswer(value)}</dd></div>)}</dl></section> : null}
                {detail.return_explanations.length ? <section className="rounded-2xl bg-amber-50 p-5 ring-1 ring-amber-200"><h2 className="font-semibold">Почему рекомендации не помогли</h2>{detail.return_explanations.map((item) => <p key={item.id} className="mt-3 whitespace-pre-wrap text-sm">Возврат {item.return_number}: {item.body}</p>)}</section> : null}
                <section className="staff-card p-6"><h2 className="text-lg font-semibold">Вложения</h2><div className="mt-4 flex flex-wrap gap-3">{detail.attachments.length ? detail.attachments.map((item, index) => <Button key={item.id} variant="outline" onClick={() => openAttachment(item.id)}>Открыть изображение {index + 1}</Button>) : <p className="text-base text-slate-500">Вложений нет.</p>}</div></section>
              </div>

              <aside className="space-y-4">
                <section className="staff-card space-y-5 border-t-4 border-t-indigo-600 p-6">
                  <h2 className="text-lg font-semibold">Триаж и маршрутизация</h2>
                  <label className="block text-sm"><span className="mb-1 block text-slate-600">Категория</span><select value={detail.category?.id ?? ""} disabled={busy} onChange={(event) => void mutate(() => operatorApi.triage(request, detail.id, { category_id: event.target.value }))} className="w-full rounded-lg border p-2"><option value="" disabled>Выберите</option>{reference?.categories.map((category) => <option key={category.id} value={category.id}>{category.name}</option>)}</select></label>
                  <label className="block text-sm"><span className="mb-1 block text-slate-600">Приоритет</span><select value={detail.priority} disabled={busy} onChange={(event) => void mutate(() => operatorApi.triage(request, detail.id, { priority: event.target.value as AppealPriority }))} className="w-full rounded-lg border p-2">{Object.entries(priorities).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
                  <div className="rounded-xl bg-indigo-50/70 p-4 text-[15px] leading-6"><p className="font-semibold text-indigo-950">Рекомендация системы</p><p className="mt-1 text-slate-600">{detail.routing.reason}</p>{detail.routing.recommended_expert ? <p className="mt-2 font-medium">{detail.routing.recommended_expert.display_name}: {detail.routing.recommended_expert.current_load}/{detail.routing.recommended_expert.capacity}</p> : null}</div>
                  <select aria-label="Эксперт" className="w-full rounded-lg border p-2 text-sm" value={selectedExpertId} onChange={(event) => setSelectedExpertId(event.target.value)}><option value="" disabled>Выберите эксперта</option>{detail.routing.candidates.map((candidate) => <option key={candidate.expert_id} value={candidate.expert_id} disabled={!candidate.available}>{candidate.display_name} — {candidate.current_load}/{candidate.capacity}</option>)}</select>
                  <Button className="w-full" size="lg" disabled={busy || !selectedExpertId || !detail.routing.candidates.some((candidate) => candidate.expert_id === selectedExpertId && candidate.available)} onClick={() => void mutate(() => operatorApi.assign(request, detail.id, selectedExpertId))}>Назначить эксперта</Button>
                </section>
                {detail.crisis_flag ? <section className="rounded-2xl border border-amber-300 bg-amber-50 p-5"><h2 className="font-semibold">Кризисный контакт</h2>{crisisContact ? <p className="mt-3 break-words rounded-lg bg-white p-3 text-sm">{crisisContact}</p> : <Button className="mt-3" variant="outline" onClick={async () => { try { setCrisisContact((await operatorApi.crisisContact(request, detail.id)).contact) } catch { setError("Контакт не указан или недоступен.") } }}>Показать отдельно</Button>}</section> : null}
                <section className="staff-card space-y-3 p-5">
                  <h2 className="font-semibold">Отклонить обращение</h2><select value={rejectKind} onChange={(event) => setRejectKind(event.target.value as typeof rejectKind)} className="w-full rounded-lg border p-2 text-sm"><option value="spam">Спам</option><option value="outside_competence">Вне компетенции</option></select>
                  <Textarea value={rejectReason} onChange={(event) => setRejectReason(event.target.value)} placeholder="Понятное заявителю объяснение" maxLength={2000} />
                  <Button variant="destructive" className="w-full" disabled={busy || !rejectReason.trim()} onClick={() => void mutate(async () => { await operatorApi.reject(request, detail.id, rejectKind, rejectReason); setRejectReason("") })}>Отклонить</Button>
                </section>
                <section className="staff-card p-5"><h2 className="font-semibold">Жалобы на сервис</h2><Button className="mt-3" variant="outline" onClick={() => void operatorApi.complaints(request, detail.id).then(setComplaints).catch(() => setError("Не удалось загрузить жалобы."))}>Показать отдельно</Button>{complaints.map((item) => <p key={item.id} className="mt-3 whitespace-pre-wrap rounded-lg bg-rose-50 p-3 text-sm">{item.body}</p>)}</section>
              </aside>
            </div>
          )}
        </section>
      </div>
    </main>
  )
}

function QueueBlock({ title, items, selectedId, onOpen }: { title: string; items: OperatorQueue["items"]; selectedId?: string; onOpen: (id: string) => Promise<void> }) {
  if (!items.length) return null
  return <section className="space-y-3"><div className="flex items-center justify-between"><h2 className="text-sm font-semibold tracking-wide text-slate-600 uppercase">{title}</h2><span className="rounded-full bg-slate-200 px-2.5 py-1 text-xs font-medium text-slate-700">{items.length}</span></div>{items.map((item) => <button key={item.id} type="button" onClick={() => void onOpen(item.id)} className={`min-h-28 w-full rounded-2xl border p-5 text-left shadow-sm transition hover:border-indigo-300 hover:shadow-md ${selectedId === item.id ? "border-indigo-400 bg-indigo-50 ring-2 ring-indigo-100" : item.crisis_flag || item.priority === "urgent" ? "border-red-200 bg-red-50/60" : "border-slate-200 bg-white"}`}><div className="flex items-start justify-between gap-3"><span className="break-safe text-[16px] font-semibold leading-6">{item.category?.name ?? "Категория не выбрана"}</span><span className="shrink-0 text-sm text-slate-500">{waiting(item.waiting_seconds)}</span></div><div className="mt-4 flex flex-wrap gap-2"><span className="inline-flex min-h-6 items-center rounded-full border border-slate-200 bg-slate-50 px-2.5 py-1 text-xs font-semibold text-slate-700">{applicantTypes[item.applicant_type] ?? item.applicant_type}</span><StatusBadge value={item.status} label={statuses[item.status] ?? item.status} /><StatusBadge value={item.priority} label={priorities[item.priority]} />{item.crisis_flag ? <StatusBadge value="crisis" /> : null}{item.is_overdue ? <StatusBadge value="overdue" /> : null}</div></button>)}</section>
}
