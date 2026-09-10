"use client"

import { useCallback, useEffect, useState } from "react"
import Link from "next/link"
import { useRouter } from "next/navigation"

import { CrisisPanel } from "@/components/appeals/crisis-panel"
import { PublicShell } from "@/components/appeals/public-shell"
import { Button } from "@/components/ui/button"
import { StatusBadge } from "@/components/ui/status-badge"
import { Textarea } from "@/components/ui/textarea"
import type { CurrentAppeal, PublicMessage } from "@/lib/appeals"
import { publicAppealsApi } from "@/lib/appeals"

export default function CurrentAppealPage() {
  const router = useRouter()
  const [appeal, setAppeal] = useState<CurrentAppeal | null>(null)
  const [messages, setMessages] = useState<PublicMessage[]>([])
  const [message, setMessage] = useState("")
  const [returnExplanation, setReturnExplanation] = useState("")
  const [rating, setRating] = useState(5)
  const [feedback, setFeedback] = useState("")
  const [complaint, setComplaint] = useState("")
  const [loading, setLoading] = useState(true)
  const [unavailable, setUnavailable] = useState(false)
  const [busy, setBusy] = useState(false)
  const [notice, setNotice] = useState("")

  const load = useCallback(async (signal?: AbortSignal) => {
    const current = await publicAppealsApi.current(signal)
    setAppeal(current)
    if (["assigned", "in_progress", "needs_clarification", "answer_ready", "completed", "returned"].includes(current.status)) {
      setMessages((await publicAppealsApi.messages(signal)).messages)
    }
  }, [])

  useEffect(() => {
    const controller = new AbortController()
    const initial = window.setTimeout(() => {
      void load(controller.signal).catch(() => setUnavailable(true)).finally(() => setLoading(false))
    }, 0)
    const timer = window.setInterval(() => void load().catch(() => undefined), 10_000)
    return () => { controller.abort(); window.clearTimeout(initial); window.clearInterval(timer) }
  }, [load])

  async function act(action: () => Promise<unknown>, success: string) {
    setBusy(true)
    setNotice("")
    try {
      await action()
      setNotice(success)
      await load()
    } catch {
      setNotice("Не удалось выполнить действие. Попробуйте ещё раз.")
    } finally {
      setBusy(false)
    }
  }

  async function leave() {
    await publicAppealsApi.leave()
    router.replace("/")
  }

  return (
    <PublicShell>
      <section className="mx-auto max-w-3xl space-y-7 py-8 sm:py-14">
        {loading ? <div className="surface-card animate-pulse p-8 text-slate-600" role="status">Загружаем статус…</div> : null}
        {unavailable ? <div className="surface-card space-y-4 p-6 sm:p-8"><h1 className="text-2xl font-semibold">Нужно снова ввести номер</h1><p className="leading-7 text-slate-600">Временный безопасный доступ закончился или не был открыт в этом браузере.</p><Link className="font-medium text-indigo-700 underline underline-offset-4" href="/appeal/check">Перейти к проверке обращения</Link></div> : null}
        {appeal ? <>
          <div className="surface-card overflow-hidden p-6 sm:p-9"><div className="-mx-9 -mt-9 mb-6 h-1.5 bg-indigo-600" /><p className="page-eyebrow">Текущий статус</p><div className="mt-3"><StatusBadge value={appeal.status} /></div><h1 className="break-safe mt-3 text-2xl font-semibold tracking-tight sm:text-3xl">{appeal.status_text}</h1>{appeal.category ? <p className="break-safe mt-4 inline-flex rounded-full border border-slate-200 bg-slate-50 px-3 py-1.5 text-sm text-slate-700">Тема: {appeal.category.name}</p> : null}<p className="mt-3 text-xs text-slate-500">Обновлено {new Date(appeal.updated_at).toLocaleString("ru-RU")}</p>{appeal.rejection_reason ? <div className="break-safe mt-5 rounded-xl bg-slate-50 p-4 text-sm leading-6">{appeal.rejection_reason}</div> : null}</div>
          <div className="surface-card p-6 sm:p-8"><h2 className="text-xl font-semibold">История статуса</h2><ol className="mt-6 space-y-6">{appeal.timeline.map((item, index) => <li key={`${item.status}-${item.occurred_at}`} className="relative flex gap-4"><span className="flex size-8 shrink-0 items-center justify-center rounded-full bg-indigo-100 text-sm font-semibold text-indigo-800 ring-4 ring-white">{index + 1}</span><div><p className="text-base font-medium leading-6">{item.text}</p><p className="mt-1 text-sm text-slate-500">{new Date(item.occurred_at).toLocaleString("ru-RU")}</p></div></li>)}</ol></div>
          {appeal.show_crisis_support ? <CrisisPanel resources={appeal.crisis_support_resources} /> : null}
          {messages.length || ["in_progress", "needs_clarification", "answer_ready"].includes(appeal.status) ? <section className="surface-card p-6 sm:p-8"><div className="flex flex-wrap items-center justify-between gap-3"><h2 className="text-xl font-semibold">Диалог со специалистом</h2><span className="rounded-full border border-indigo-100 bg-indigo-50 px-2.5 py-1 text-xs font-semibold text-indigo-700">Конфиденциально</span></div><div className="my-6 space-y-4">{messages.map((item) => <div key={item.id} className={`break-safe max-w-[92%] rounded-2xl border p-4 text-base leading-7 ${item.author_type === "applicant" ? "ml-auto border-indigo-100 bg-indigo-50" : "mr-auto border-slate-200 bg-white"}`}><p className="mb-1 text-sm font-medium text-slate-500">{item.author_label}</p><p className="whitespace-pre-wrap">{item.body}</p></div>)}</div>{["in_progress", "needs_clarification"].includes(appeal.status) ? <><Textarea className="min-h-32" value={message} onChange={(event) => setMessage(event.target.value)} maxLength={5000} placeholder="Напишите специалисту"/><Button className="mt-3 w-full sm:w-auto" size="lg" disabled={busy || !message.trim()} onClick={() => void act(() => publicAppealsApi.sendMessage(message), "Сообщение отправлено.").then(() => setMessage(""))}>Отправить сообщение</Button></> : null}</section> : null}
          {appeal.status === "answer_ready" ? <section className="space-y-3 rounded-2xl bg-indigo-50 p-6 ring-1 ring-indigo-200"><h2 className="font-semibold">Помогли ли рекомендации?</h2><div className="flex gap-2"><Button disabled={busy} onClick={() => void act(() => publicAppealsApi.resolve("helped"), "Спасибо! Обращение завершено.")}>Это помогло</Button></div><Textarea value={returnExplanation} onChange={(event) => setReturnExplanation(event.target.value)} maxLength={2000} placeholder="Если не помогло, расскажите, чего не хватило"/><Button variant="outline" disabled={busy || !returnExplanation.trim() || appeal.return_count >= appeal.max_returns} onClick={() => void act(() => publicAppealsApi.resolve("not_helped", returnExplanation), "Обращение возвращено оператору.")}>Это не помогло</Button>{appeal.return_count >= appeal.max_returns ? <p className="text-sm text-slate-600">Лимит возвратов исчерпан. Вы всё ещё можете оставить жалобу.</p> : null}</section> : null}
          {["completed", "returned"].includes(appeal.status) ? <section className="surface-card space-y-3 p-6"><h2 className="font-semibold">Оценка помощи</h2><select aria-label="Оценка" value={rating} onChange={(event) => setRating(Number(event.target.value))} className="h-11 rounded-xl border px-3">{[5,4,3,2,1].map((value) => <option key={value} value={value}>{value} из 5</option>)}</select><Textarea value={feedback} onChange={(event) => setFeedback(event.target.value)} maxLength={2000} placeholder="Комментарий — необязательно"/><Button variant="outline" disabled={busy} onClick={() => void act(() => publicAppealsApi.feedback(rating, feedback), "Спасибо за обратную связь.")}>Отправить оценку</Button></section> : null}
          <details className="surface-card p-6"><summary className="cursor-pointer rounded-md font-semibold focus-visible:outline-offset-4">Пожаловаться на работу сервиса</summary><div className="mt-4 space-y-3"><p className="text-sm text-slate-600">Жалоба не будет показана специалисту.</p><Textarea value={complaint} onChange={(event) => setComplaint(event.target.value)} maxLength={3000}/><Button variant="outline" disabled={busy || !complaint.trim()} onClick={() => void act(() => publicAppealsApi.complaint(complaint), "Жалоба принята.").then(() => setComplaint(""))}>Отправить жалобу</Button></div></details>
          {notice ? <p className="rounded-xl border border-slate-200 bg-white p-4 text-sm" role="status">{notice}</p> : null}
          <Button type="button" variant="outline" className="w-full" onClick={leave}>Закрыть доступ на этом устройстве</Button>
        </> : null}
      </section>
    </PublicShell>
  )
}
