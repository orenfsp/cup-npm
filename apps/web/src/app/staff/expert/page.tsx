"use client"

import { useCallback, useEffect, useState } from "react"
import { useRouter } from "next/navigation"

import { Button } from "@/components/ui/button"
import { StaffHeader } from "@/components/staff/staff-header"
import { StatusBadge } from "@/components/ui/status-badge"
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
      <div className="mx-auto grid w-full max-w-[1600px] gap-6 p-4 sm:p-6 lg:p-8 xl:grid-cols-[minmax(300px,0.28fr)_minmax(0,0.72fr)] xl:px-10">
        <aside className="space-y-4">
          <select aria-label="Статус" value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)} className="w-full rounded-xl border bg-white p-3 text-sm">
            <option value="">Все активные</option><option value="assigned">Новые назначенные</option><option value="in_progress">В работе</option><option value="needs_clarification">Нужно уточнение</option><option value="answer_ready">Ответ готов</option>
          </select>
          {items.map((item) => <button key={item.id} type="button" onClick={() => { void releaseComposer(); void loadDetail(item.id) }} className={`min-h-28 w-full rounded-2xl border p-5 text-left shadow-sm transition hover:border-indigo-300 hover:shadow-md ${detail?.id === item.id ? "border-indigo-400 bg-indigo-50 ring-2 ring-indigo-100" : item.crisis_flag || item.priority === "urgent" ? "border-red-200 bg-red-50/60" : "border-slate-200 bg-white"}`}>
            <p className="break-safe text-[16px] font-semibold leading-6">{item.category?.name ?? "Без категории"}</p><div className="mt-4 flex flex-wrap gap-2"><StatusBadge value={item.status} label={statusLabels[item.status]} /><span className="inline-flex min-h-6 items-center rounded-full border border-slate-200 bg-white px-2.5 py-1 text-xs font-semibold text-slate-600">{waiting(item.waiting_seconds)}</span>{item.priority === "urgent" ? <StatusBadge value="urgent" /> : null}{item.crisis_flag ? <StatusBadge value="crisis" label="Требует внимания" /> : null}</div>
          </button>)}
        </aside>
        <section className="min-w-0 space-y-6">
          {error ? <p className="state-error" role="alert">{error}</p> : null}
          {!detail ? <div className="staff-card p-12 text-center text-base text-slate-500">Выберите назначенное вам обращение.</div> : <>
            <section className="staff-card border-t-4 border-t-indigo-600 p-6 sm:p-8"><div className="flex flex-wrap items-center justify-between gap-4"><div><p className="text-sm font-semibold text-indigo-700">{statusLabels[detail.status]}</p><h2 className="mt-1 text-2xl font-semibold tracking-tight">{detail.category?.name ?? "Без категории"}</h2></div>{detail.status === "assigned" ? <Button size="lg" disabled={busy} onClick={() => void mutate(() => expertApi.take(request, detail.id))}>Взять в работу</Button> : null}</div><p className="break-safe mt-6 whitespace-pre-wrap text-[17px] leading-8 text-slate-800">{detail.description ?? "Описание не добавлено."}</p>{Object.entries(detail.intake_answers).map(([key, value]) => <p key={key} className="break-safe mt-4 rounded-xl bg-slate-50 p-4 text-[15px] leading-6"><span className="font-medium text-slate-500">{key}: </span>{Array.isArray(value) ? value.join(", ") : typeof value === "boolean" ? (value ? "Да" : "Нет") : value}</p>)}</section>
            <div className="grid gap-6 min-[1500px]:grid-cols-[minmax(0,1.6fr)_minmax(320px,0.8fr)]">
              <section className="staff-card flex min-h-[560px] flex-col p-6 min-[1500px]:row-span-4 sm:p-7"><div className="flex flex-wrap items-center justify-between gap-3"><h2 className="text-xl font-semibold">Диалог с заявителем</h2><span className="rounded-full bg-indigo-50 px-3 py-1.5 text-sm font-medium text-indigo-700">Виден заявителю</span></div><div className="soft-scrollbar my-6 min-h-64 flex-1 space-y-4 overflow-y-auto pr-1">{detail.messages.map((item) => <div key={item.id} className={`break-safe max-w-[88%] rounded-2xl border p-4 text-base leading-7 ${item.author_type === "specialist" ? "ml-auto border-indigo-100 bg-indigo-50" : "mr-auto border-slate-200 bg-white shadow-sm"}`}><p className="mb-1 text-sm font-medium text-slate-500">{item.author_label}</p><p className="whitespace-pre-wrap">{item.body}</p></div>)}</div><Textarea className="min-h-36 text-base" value={message} onFocus={() => void acquireComposer()} onChange={(event) => setMessage(event.target.value)} placeholder="Сообщение заявителю" maxLength={5000}/><div className="mt-4 flex flex-col gap-3 sm:flex-row"><Button size="lg" disabled={busy || !lockHeld || !message.trim()} onClick={() => void mutate(() => expertApi.message(request, detail.id, message), () => { setMessage(""); void releaseComposer() })}>Отправить ответ</Button><Button variant="outline" disabled={busy || !lockHeld} onClick={() => void mutate(() => expertApi.clarify(request, detail.id, message.trim() || null), () => { setMessage(""); void releaseComposer() })}>Запросить уточнение</Button></div>{!lockHeld ? <p className="mt-3 text-sm text-slate-500">Нажмите в поле, чтобы занять редактор ответа.</p> : <p className="mt-3 text-sm font-medium text-indigo-700">Редактор закреплён за вами.</p>}</section>
              <section className="rounded-2xl border border-amber-200 bg-amber-50/70 p-6"><div className="flex flex-wrap items-center justify-between gap-3"><h2 className="text-lg font-semibold text-amber-950">Внутренние заметки</h2><span className="rounded-full border border-amber-200 bg-white px-2.5 py-1 text-xs font-semibold text-amber-900">Только для команды</span></div><div className="soft-scrollbar my-4 max-h-72 space-y-3 overflow-y-auto">{detail.internal_notes.map((item) => <div key={item.id} className="rounded-xl border border-amber-100 bg-white p-4 text-[15px]"><p className="text-sm font-medium text-amber-800">Внутренняя заметка · {item.author_label}</p><p className="break-safe mt-2 whitespace-pre-wrap leading-6">{item.body}</p></div>)}</div><Textarea className="min-h-32" value={note} onChange={(event) => setNote(event.target.value)} placeholder="Внутренняя заметка" maxLength={5000}/><Button className="mt-4" variant="outline" disabled={busy || !note.trim()} onClick={() => void mutate(() => expertApi.note(request, detail.id, note), () => setNote(""))}>Добавить заметку</Button></section>
              <section className="staff-card p-6"><h2 className="text-lg font-semibold">Материалы</h2><div className="mt-4 flex flex-wrap gap-2">{detail.attachments.length ? detail.attachments.map((item, index) => <Button key={item.id} variant="outline" onClick={() => void openAttachment(item.id)}>Открыть изображение {index + 1}</Button>) : <p className="text-[15px] text-slate-500">Вложений нет.</p>}</div></section>
              <section className="staff-card space-y-4 border-t-4 border-t-indigo-500 p-6"><h2 className="text-lg font-semibold">Работа с обращением</h2><select aria-label="Специалист" value={target} onChange={(event) => setTarget(event.target.value)} className="w-full"><option value="">Выберите специалиста</option>{detail.collaboration_candidates.map((item) => <option key={item.expert_id} value={item.expert_id} disabled={!item.available}>{item.display_name} — {item.current_load}/{item.capacity}</option>)}</select><Textarea className="min-h-28" value={reason} onChange={(event) => setReason(event.target.value)} placeholder="Причина подключения или передачи" maxLength={2000}/><div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap"><Button variant="outline" disabled={busy || !detail.is_primary || !target || !reason.trim()} onClick={() => void mutate(() => expertApi.coexecutor(request, detail.id, target, reason), () => setReason(""))}>Подключить соисполнителя</Button><Button variant="outline" disabled={busy || !detail.is_primary || !target || !reason.trim()} onClick={() => void mutate(() => expertApi.transfer(request, detail.id, target, reason), () => setReason(""))}>Запросить передачу</Button></div><Textarea className="min-h-36" value={recommendation} onFocus={() => void acquireComposer()} onChange={(event) => setRecommendation(event.target.value)} placeholder="Итоговые рекомендации" maxLength={5000}/><Button className="w-full" size="lg" disabled={busy || !lockHeld || !recommendation.trim()} onClick={() => void mutate(() => expertApi.recommendations(request, detail.id, recommendation), () => { setRecommendation(""); void releaseComposer() })}>Подготовить рекомендации</Button></section>
              {detail.is_primary && ["assigned", "in_progress", "needs_clarification"].includes(detail.status) ? <section className="rounded-2xl border border-slate-200 bg-white p-5"><h2 className="text-base font-semibold text-slate-800">Не могу взять обращение</h2><Textarea className="mt-3 min-h-24" value={cannotTakeReason} onChange={(event) => setCannotTakeReason(event.target.value)} placeholder="Причина для оператора" maxLength={2000}/><Button className="mt-3" size="sm" variant="destructive" disabled={busy || !cannotTakeReason.trim()} onClick={() => void mutate(() => expertApi.cannotTake(request, detail.id, cannotTakeReason), () => setCannotTakeReason(""))}>Отправить запрос оператору</Button></section> : null}
            </div>
          </>}
        </section>
      </div>
    </main>
  )
}
