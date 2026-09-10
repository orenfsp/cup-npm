"use client"

import { useCallback, useEffect, useMemo, useState } from "react"
import { useRouter } from "next/navigation"

import { Button } from "@/components/ui/button"
import { StaffHeader } from "@/components/staff/staff-header"
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

      <div className="mx-auto grid max-w-7xl gap-5 p-4 sm:p-6 lg:grid-cols-[360px_1fr]">
        <aside className="space-y-4">
          {transfers.length ? <section className="space-y-2 rounded-xl bg-indigo-50 p-3 ring-1 ring-indigo-200"><h2 className="text-sm font-semibold">Запросы на передачу</h2>{transfers.map((item) => { const selected = transferTargets[item.id] ?? item.target_expert_id ?? ""; return <div key={item.id} className="rounded-lg bg-white p-3 text-sm"><p className="font-medium">{item.request_kind === "cannot_take" ? "Не может взять обращение" : "Передача другому специалисту"}</p><p className="mt-1"><span className="font-medium">{item.requester_display_name}</span>{item.target_display_name ? ` → ${item.target_display_name}` : " — оператор выбирает замену"}</p><p className="mt-1 text-slate-600">{item.reason}</p><select aria-label="Эксперт на замену" className="mt-2 w-full rounded-lg border p-2" value={selected} onChange={(event) => setTransferTargets((current) => ({ ...current, [item.id]: event.target.value }))}><option value="">Выберите подходящего эксперта</option>{item.eligible_experts.map((candidate) => <option key={candidate.expert_id} value={candidate.expert_id} disabled={!candidate.available}>{candidate.display_name} — {candidate.current_load}/{candidate.capacity}</option>)}</select><div className="mt-2 flex gap-2"><Button size="sm" disabled={busy || !selected} onClick={() => void operatorApi.resolveTransfer(request, item.id, "approve", selected).then(async () => { setTransfers(await operatorApi.transferRequests(request)); await loadQueue() }).catch(() => setError("Не удалось подтвердить передачу."))}>Подтвердить</Button><Button size="sm" variant="outline" disabled={busy} onClick={() => void operatorApi.resolveTransfer(request, item.id, "reject").then(async () => setTransfers(await operatorApi.transferRequests(request))).catch(() => setError("Не удалось отклонить передачу."))}>Отклонить</Button></div></div> })}</section> : null}
          <div className="grid grid-cols-2 gap-2">
            {queue ? ([
              ["Требуют внимания", queue.counters.crisis, "bg-amber-50"],
              ["Новые", queue.counters.new, "bg-white"],
              ["Возвращённые", queue.counters.returned, "bg-white"],
              ["Просроченные", queue.counters.overdue, "bg-white"],
            ] as const).map(([label, value, style]) => (
              <div key={label} className={`rounded-xl p-3 ring-1 ring-slate-200 ${style}`}><p className="text-2xl font-semibold">{value}</p><p className="text-xs">{label}</p></div>
            )) : null}
          </div>
          <div className="staff-card grid grid-cols-2 gap-2 p-3">
            <select aria-label="Статус" value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)} className="rounded-lg border p-2 text-sm">
              <option value="">Новые и возвращённые</option><option value="new">Новые</option><option value="returned">Возвращённые</option>
            </select>
            <select aria-label="Приоритет" value={priorityFilter} onChange={(event) => setPriorityFilter(event.target.value)} className="rounded-lg border p-2 text-sm">
              <option value="">Все приоритеты</option><option value="urgent">Срочный</option><option value="standard">Обычный</option><option value="low">Низкий</option>
            </select>
            <label className="col-span-2 flex items-center gap-2 text-sm"><input type="checkbox" checked={crisisOnly} onChange={(event) => setCrisisOnly(event.target.checked)} /> Только требующие внимания</label>
          </div>
          <QueueBlock title="Требуют внимания" items={crisisItems} selectedId={detail?.id} onOpen={loadDetail} />
          <QueueBlock title="Очередь" items={regularItems} selectedId={detail?.id} onOpen={loadDetail} />
        </aside>

        <section className="min-w-0">
          {error ? <p className="mb-4 rounded-xl bg-rose-50 p-4 text-sm text-rose-800">{error}</p> : null}
          {!detail ? <div className="staff-card p-10 text-center text-slate-500">Выберите обращение в очереди.</div> : (
            <div className="grid gap-5 xl:grid-cols-[1fr_320px]">
              <div className="space-y-5">
                <section className="staff-card p-5 sm:p-6">
                  <div className="flex flex-wrap gap-2 text-xs"><span>{applicantTypes[detail.applicant_type] ?? detail.applicant_type}</span><span>{statuses[detail.status] ?? detail.status}</span><span>ожидает {waiting(detail.waiting_seconds)}</span>{detail.crisis_flag ? <span className="rounded-full bg-amber-100 px-2 py-1 text-amber-900">Требует внимания</span> : null}</div>
                  <h2 className="mt-5 text-lg font-semibold">Описание ситуации</h2><p className="mt-3 whitespace-pre-wrap leading-7 text-slate-700">{detail.description || "Описание не добавлено."}</p>
                </section>
                {Object.keys(detail.intake_answers).length ? <section className="staff-card p-5"><h2 className="font-semibold">Дополнительные ответы</h2><dl className="mt-4 space-y-3">{Object.entries(detail.intake_answers).map(([key, value]) => <div key={key}><dt className="text-xs text-slate-500">{intakeLabels[key] ?? key}</dt><dd className="mt-1 text-sm">{renderAnswer(value)}</dd></div>)}</dl></section> : null}
                {detail.return_explanations.length ? <section className="rounded-2xl bg-amber-50 p-5 ring-1 ring-amber-200"><h2 className="font-semibold">Почему рекомендации не помогли</h2>{detail.return_explanations.map((item) => <p key={item.id} className="mt-3 whitespace-pre-wrap text-sm">Возврат {item.return_number}: {item.body}</p>)}</section> : null}
                <section className="staff-card p-5"><h2 className="font-semibold">Вложения</h2><div className="mt-3 flex flex-wrap gap-2">{detail.attachments.length ? detail.attachments.map((item, index) => <Button key={item.id} variant="outline" onClick={() => openAttachment(item.id)}>Открыть изображение {index + 1}</Button>) : <p className="text-sm text-slate-500">Вложений нет.</p>}</div></section>
              </div>

              <aside className="space-y-4">
                <section className="staff-card space-y-4 border-t-4 border-t-teal-600 p-5">
                  <h2 className="font-semibold">Триаж и маршрутизация</h2>
                  <label className="block text-sm"><span className="mb-1 block text-slate-600">Категория</span><select value={detail.category?.id ?? ""} disabled={busy} onChange={(event) => void mutate(() => operatorApi.triage(request, detail.id, { category_id: event.target.value }))} className="w-full rounded-lg border p-2"><option value="" disabled>Выберите</option>{reference?.categories.map((category) => <option key={category.id} value={category.id}>{category.name}</option>)}</select></label>
                  <label className="block text-sm"><span className="mb-1 block text-slate-600">Приоритет</span><select value={detail.priority} disabled={busy} onChange={(event) => void mutate(() => operatorApi.triage(request, detail.id, { priority: event.target.value as AppealPriority }))} className="w-full rounded-lg border p-2">{Object.entries(priorities).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
                  <div className="rounded-xl bg-slate-50 p-3 text-sm"><p className="font-medium">Рекомендация</p><p className="mt-1 text-slate-600">{detail.routing.reason}</p>{detail.routing.recommended_expert ? <p className="mt-2">{detail.routing.recommended_expert.display_name}: {detail.routing.recommended_expert.current_load}/{detail.routing.recommended_expert.capacity}</p> : null}</div>
                  <select aria-label="Эксперт" className="w-full rounded-lg border p-2 text-sm" value={selectedExpertId} onChange={(event) => setSelectedExpertId(event.target.value)}><option value="" disabled>Выберите эксперта</option>{detail.routing.candidates.map((candidate) => <option key={candidate.expert_id} value={candidate.expert_id} disabled={!candidate.available}>{candidate.display_name} — {candidate.current_load}/{candidate.capacity}</option>)}</select>
                  <Button className="w-full" disabled={busy || !selectedExpertId || !detail.routing.candidates.some((candidate) => candidate.expert_id === selectedExpertId && candidate.available)} onClick={() => void mutate(() => operatorApi.assign(request, detail.id, selectedExpertId))}>Назначить эксперта</Button>
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
  return <section className="space-y-2"><div className="flex items-center justify-between"><h2 className="text-xs font-semibold tracking-wide text-slate-500 uppercase">{title}</h2><span className="rounded-full bg-slate-200 px-2 py-0.5 text-xs font-medium text-slate-700">{items.length}</span></div>{items.map((item) => <button key={item.id} type="button" onClick={() => void onOpen(item.id)} className={`w-full rounded-2xl border p-4 text-left shadow-sm transition hover:-translate-y-0.5 hover:shadow-md ${selectedId === item.id ? "border-teal-400 bg-teal-50 ring-2 ring-teal-200" : item.crisis_flag || item.priority === "urgent" ? "border-amber-200 bg-amber-50" : "border-slate-200 bg-white"}`}><div className="flex items-center justify-between gap-2"><span className="font-medium">{item.category?.name ?? "Категория не выбрана"}</span><span className="shrink-0 text-xs text-slate-500">{waiting(item.waiting_seconds)}</span></div><div className="mt-2 flex flex-wrap gap-1.5 text-xs"><span className="rounded-full bg-slate-100 px-2 py-1 text-slate-700">{applicantTypes[item.applicant_type] ?? item.applicant_type}</span><span className="rounded-full bg-slate-100 px-2 py-1 text-slate-700">{statuses[item.status] ?? item.status}</span><span className="rounded-full bg-slate-100 px-2 py-1 text-slate-700">{priorities[item.priority]}</span>{item.is_overdue ? <span className="rounded-full bg-rose-100 px-2 py-1 font-medium text-rose-700">Просрочено</span> : null}</div></button>)}</section>
}
