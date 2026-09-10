"use client"

import { useCallback, useEffect, useState } from "react"
import { useRouter } from "next/navigation"

import { Button } from "@/components/ui/button"
import { StaffHeader } from "@/components/staff/staff-header"
import { Textarea } from "@/components/ui/textarea"
import { useAuth } from "@/lib/auth"
import { expertApi, type ExpertDetail, type ExpertQueueItem } from "@/lib/expert"

const statusLabels: Record<string, string> = {
  assigned: "Новое назначение",
  in_progress: "В работе",
  needs_clarification: "Нужно уточнение",
  answer_ready: "Ответ готов",
}

function waiting(seconds: number) {
  const hours = Math.floor(seconds / 3600)
  return hours < 1 ? `${Math.max(1, Math.floor(seconds / 60))} мин.` : `${hours} ч.`
}

export default function ExpertWorkspacePage() {
  const router = useRouter()
  const { staff, status, request, logout } = useAuth()
  const [items, setItems] = useState<ExpertQueueItem[]>([])
  const [detail, setDetail] = useState<ExpertDetail | null>(null)
  const [statusFilter, setStatusFilter] = useState("")
  const [message, setMessage] = useState("")
  const [recommendation, setRecommendation] = useState("")
  const [note, setNote] = useState("")
  const [reason, setReason] = useState("")
  const [cannotTakeReason, setCannotTakeReason] = useState("")
  const [target, setTarget] = useState("")
  const [error, setError] = useState("")
  const [busy, setBusy] = useState(false)
  const [lockHeld, setLockHeld] = useState(false)

  useEffect(() => {
    if (status === "anonymous") router.replace("/staff/login")
    if (status === "authenticated" && staff?.must_change_password) router.replace("/staff/change-password")
    else if (status === "authenticated" && staff?.role !== "expert") router.replace(`/staff/${staff?.role}`)
  }, [router, staff, status])

  const loadQueue = useCallback(async () => {
    const query = statusFilter ? `?status=${statusFilter}` : ""
    setItems((await expertApi.queue(request, query)).items)
  }, [request, statusFilter])

  const loadDetail = useCallback(async (appealId: string) => {
    setError("")
    setDetail(await expertApi.detail(request, appealId))
  }, [request])

  useEffect(() => {
    if (status !== "authenticated" || staff?.role !== "expert" || staff.must_change_password) return
    const initial = window.setTimeout(() => {
      void loadQueue().catch(() => setError("Не удалось загрузить обращения."))
    }, 0)
    const timer = window.setInterval(() => {
      void loadQueue()
      if (detail?.id) void loadDetail(detail.id)
    }, 10_000)
    return () => { window.clearTimeout(initial); window.clearInterval(timer) }
  }, [detail?.id, loadDetail, loadQueue, staff?.must_change_password, staff?.role, status])

  useEffect(() => {
    if (!lockHeld || !detail) return
    const timer = window.setInterval(() => {
      void expertApi.heartbeatLock(request, detail.id).catch(() => {
        setLockHeld(false)
        setError("Редактор ответа освободился. Откройте его снова перед отправкой.")
      })
    }, 15_000)
    return () => window.clearInterval(timer)
  }, [detail, lockHeld, request])

  async function mutate(action: () => Promise<unknown>, clear?: () => void) {
    if (!detail) return
    setBusy(true)
    setError("")
    try {
      await action()
      clear?.()
      await Promise.all([loadQueue(), loadDetail(detail.id)])
    } catch {
      setError("Действие не выполнено. Проверьте статус обращения и права доступа.")
    } finally {
      setBusy(false)
    }
  }

  async function acquireComposer() {
    if (!detail || lockHeld) return
    try {
      await expertApi.acquireLock(request, detail.id)
      setLockHeld(true)
    } catch {
      setError("Другой специалист сейчас готовит ответ. Попробуйте немного позже.")
    }
  }

  async function releaseComposer() {
    if (detail && lockHeld) await expertApi.releaseLock(request, detail.id).catch(() => undefined)
    setLockHeld(false)
  }

  async function openAttachment(id: string) {
    if (!detail) return
    try {
      const blob = await expertApi.attachment(request, detail.id, id)
      const url = URL.createObjectURL(blob)
      window.open(url, "_blank", "noopener,noreferrer")
      window.setTimeout(() => URL.revokeObjectURL(url), 60_000)
    } catch {
      setError("Вложение недоступно.")
    }
  }

  if (status === "checking") return <main className="m-auto p-6 text-sm">Проверяем сессию…</main>
  if (status !== "authenticated" || staff?.role !== "expert") return null

  return (
    <main className="staff-workspace">
      <StaffHeader title="Рабочее место специалиста" role="Эксперт" name={staff.display_name} onLogout={() => { void logout().finally(() => router.replace("/staff/login")) }} />
      <div className="mx-auto grid max-w-7xl gap-5 p-4 sm:p-6 lg:grid-cols-[330px_1fr]">
        <aside className="space-y-3">
          <select aria-label="Статус" value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)} className="w-full rounded-xl border bg-white p-3 text-sm">
            <option value="">Все активные</option><option value="assigned">Новые назначенные</option><option value="in_progress">В работе</option><option value="needs_clarification">Нужно уточнение</option><option value="answer_ready">Ответ готов</option>
          </select>
          {items.map((item) => <button key={item.id} type="button" onClick={() => { void releaseComposer(); void loadDetail(item.id) }} className={`w-full rounded-2xl border p-4 text-left shadow-sm transition hover:-translate-y-0.5 hover:shadow-md ${detail?.id === item.id ? "border-teal-400 bg-teal-50 ring-2 ring-teal-200" : item.crisis_flag || item.priority === "urgent" ? "border-amber-200 bg-amber-50" : "border-slate-200 bg-white"}`}>
            <p className="font-medium">{item.category?.name ?? "Без категории"}</p><div className="mt-2 flex flex-wrap gap-1.5 text-xs"><span className="rounded-full bg-white/80 px-2 py-1 text-slate-700">{statusLabels[item.status]}</span><span className="rounded-full bg-white/80 px-2 py-1 text-slate-700">{waiting(item.waiting_seconds)}</span>{item.crisis_flag ? <span className="rounded-full bg-amber-200/70 px-2 py-1 font-medium text-amber-950">Требует внимания</span> : null}</div>
          </button>)}
        </aside>
        <section className="min-w-0 space-y-4">
          {error ? <p className="rounded-xl bg-rose-50 p-4 text-sm text-rose-800">{error}</p> : null}
          {!detail ? <div className="staff-card p-10 text-center text-slate-500">Выберите назначенное вам обращение.</div> : <>
            <section className="staff-card border-t-4 border-t-teal-600 p-5 sm:p-6"><div className="flex flex-wrap items-center justify-between gap-3"><div><p className="text-sm font-medium text-teal-700">{statusLabels[detail.status]}</p><h2 className="text-xl font-semibold tracking-tight">{detail.category?.name ?? "Без категории"}</h2></div>{detail.status === "assigned" ? <Button disabled={busy} onClick={() => void mutate(() => expertApi.take(request, detail.id))}>Взять в работу</Button> : null}</div><p className="mt-5 whitespace-pre-wrap leading-7">{detail.description ?? "Описание не добавлено."}</p>{Object.entries(detail.intake_answers).map(([key, value]) => <p key={key} className="mt-3 rounded-lg bg-slate-50 p-3 text-sm"><span className="text-slate-500">{key}: </span>{Array.isArray(value) ? value.join(", ") : typeof value === "boolean" ? (value ? "Да" : "Нет") : value}</p>)}</section>
            {detail.is_primary && ["assigned", "in_progress", "needs_clarification"].includes(detail.status) ? <section className="rounded-2xl border border-amber-200 bg-amber-50 p-5"><h2 className="font-semibold">Не могу взять обращение</h2><p className="mt-1 text-sm text-slate-600">Обращение останется за вами, пока оператор не выберет замену.</p><Textarea className="mt-3" value={cannotTakeReason} onChange={(event) => setCannotTakeReason(event.target.value)} placeholder="Обязательная причина для оператора" maxLength={2000}/><Button className="mt-3" variant="outline" disabled={busy || !cannotTakeReason.trim()} onClick={() => void mutate(() => expertApi.cannotTake(request, detail.id, cannotTakeReason), () => setCannotTakeReason(""))}>Отправить запрос оператору</Button></section> : null}
            <div className="grid gap-4 xl:grid-cols-2">
              <section className="staff-card p-5"><div className="flex items-center justify-between gap-3"><h2 className="font-semibold">Диалог с заявителем</h2><span className="rounded-full bg-teal-50 px-2.5 py-1 text-xs text-teal-700">Виден заявителю</span></div><div className="soft-scrollbar my-4 max-h-80 space-y-3 overflow-y-auto">{detail.messages.map((item) => <div key={item.id} className={`rounded-xl p-3 text-sm ${item.author_type === "specialist" ? "ml-8 bg-teal-50" : "mr-8 bg-slate-100"}`}><p className="mb-1 text-xs font-medium text-slate-500">{item.author_label}</p><p className="whitespace-pre-wrap">{item.body}</p></div>)}</div><Textarea value={message} onFocus={() => void acquireComposer()} onChange={(event) => setMessage(event.target.value)} placeholder="Сообщение заявителю" maxLength={5000}/><div className="mt-3 flex flex-wrap gap-2"><Button disabled={busy || !lockHeld || !message.trim()} onClick={() => void mutate(() => expertApi.message(request, detail.id, message), () => { setMessage(""); void releaseComposer() })}>Отправить</Button><Button variant="outline" disabled={busy || !lockHeld} onClick={() => void mutate(() => expertApi.clarify(request, detail.id, message.trim() || null), () => { setMessage(""); void releaseComposer() })}>Запросить уточнение</Button></div>{!lockHeld ? <p className="mt-2 text-xs text-slate-500">Нажмите в поле, чтобы занять редактор ответа.</p> : <p className="mt-2 text-xs font-medium text-teal-700">Редактор закреплён за вами.</p>}</section>
              <section className="rounded-2xl border-2 border-dashed border-indigo-200 bg-indigo-50/40 p-5"><h2 className="font-semibold text-indigo-950">Внутренние заметки</h2><p className="mt-1 text-xs text-indigo-700">Не видны заявителю.</p><div className="my-4 max-h-64 space-y-2 overflow-y-auto">{detail.internal_notes.map((item) => <div key={item.id} className="rounded-lg bg-white p-3 text-sm"><p className="text-xs text-slate-500">{item.author_label}</p><p className="mt-1 whitespace-pre-wrap">{item.body}</p></div>)}</div><Textarea value={note} onChange={(event) => setNote(event.target.value)} placeholder="Внутренняя заметка" maxLength={5000}/><Button className="mt-3" variant="outline" disabled={busy || !note.trim()} onClick={() => void mutate(() => expertApi.note(request, detail.id, note), () => setNote(""))}>Добавить заметку</Button></section>
              <section className="staff-card p-5"><h2 className="font-semibold">Материалы / вложения</h2><div className="mt-3 flex flex-wrap gap-2">{detail.attachments.length ? detail.attachments.map((item, index) => <Button key={item.id} variant="outline" onClick={() => void openAttachment(item.id)}>Открыть изображение {index + 1}</Button>) : <p className="text-sm text-slate-500">Вложений нет.</p>}</div></section>
              <section className="staff-card space-y-3 border-t-4 border-t-indigo-500 p-5"><h2 className="font-semibold">Работа с обращением</h2><select aria-label="Специалист" value={target} onChange={(event) => setTarget(event.target.value)} className="w-full rounded-lg border p-2 text-sm"><option value="">Выберите специалиста</option>{detail.collaboration_candidates.map((item) => <option key={item.expert_id} value={item.expert_id} disabled={!item.available}>{item.display_name} — {item.current_load}/{item.capacity}</option>)}</select><Textarea value={reason} onChange={(event) => setReason(event.target.value)} placeholder="Причина подключения или передачи" maxLength={2000}/><div className="flex flex-wrap gap-2"><Button variant="outline" disabled={busy || !detail.is_primary || !target || !reason.trim()} onClick={() => void mutate(() => expertApi.coexecutor(request, detail.id, target, reason), () => setReason(""))}>Подключить соисполнителя</Button><Button variant="outline" disabled={busy || !detail.is_primary || !target || !reason.trim()} onClick={() => void mutate(() => expertApi.transfer(request, detail.id, target, reason), () => setReason(""))}>Запросить передачу</Button></div><Textarea value={recommendation} onFocus={() => void acquireComposer()} onChange={(event) => setRecommendation(event.target.value)} placeholder="Итоговые рекомендации" maxLength={5000}/><Button className="w-full" disabled={busy || !lockHeld || !recommendation.trim()} onClick={() => void mutate(() => expertApi.recommendations(request, detail.id, recommendation), () => { setRecommendation(""); void releaseComposer() })}>Подготовить рекомендации</Button></section>
            </div>
          </>}
        </section>
      </div>
    </main>
  )
}
