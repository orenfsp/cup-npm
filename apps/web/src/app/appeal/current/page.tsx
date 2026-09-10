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

    if (
      [
        "assigned",
        "in_progress",
        "needs_clarification",
        "answer_ready",
        "completed",
        "returned",
      ].includes(current.status)
    ) {
      setMessages(
        (await publicAppealsApi.messages(signal)).messages,
      )
    }
  }, [])

  useEffect(() => {
    const controller = new AbortController()

    const initial = window.setTimeout(() => {
      void load(controller.signal)
        .catch(() => setUnavailable(true))
        .finally(() => setLoading(false))
    }, 0)

    const timer = window.setInterval(
      () => void load().catch(() => undefined),
      10_000,
    )

    return () => {
      controller.abort()
      window.clearTimeout(initial)
      window.clearInterval(timer)
    }
  }, [load])

  async function act(
    action: () => Promise<unknown>,
    success: string,
  ) {
    setBusy(true)
    setNotice("")

    try {
      await action()
      setNotice(success)
      await load()
    } catch {
      setNotice(
        "Не удалось выполнить действие. Попробуйте ещё раз.",
      )
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
      <section className="mx-auto w-full max-w-3xl space-y-6 py-8 sm:space-y-7 sm:py-14">
        {/* LOADING */}
        {loading ? (
          <div
            className="surface-card flex items-center gap-4 rounded-[26px] p-6 shadow-[0_20px_60px_rgba(68,53,126,.07)] sm:p-8"
            role="status"
          >
            <div className="h-10 w-10 shrink-0 animate-pulse rounded-full bg-[#ece9ff]" />

            <div className="space-y-2">
              <div className="h-4 w-36 animate-pulse rounded-full bg-[#eeeaf8]" />
              <div className="h-3 w-52 animate-pulse rounded-full bg-[#f1eff5]" />
            </div>
          </div>
        ) : null}

        {/* UNAVAILABLE */}
        {unavailable ? (
          <div className="surface-card relative overflow-hidden rounded-[28px] p-6 shadow-[0_20px_60px_rgba(68,53,126,.08)] sm:p-8">
            <div
              aria-hidden="true"
              className="pointer-events-none absolute -right-24 -top-24 h-56 w-56 rounded-full bg-violet-300/15 blur-3xl"
            />

            <div className="relative">
              <div className="mb-5 flex h-12 w-12 items-center justify-center rounded-[16px] bg-[#eeeaff] text-[#6754f7]">
                <svg
                  width="22"
                  height="22"
                  viewBox="0 0 24 24"
                  fill="none"
                  aria-hidden="true"
                >
                  <path
                    d="M12 9v4"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                  />
                  <path
                    d="M12 17h.01"
                    stroke="currentColor"
                    strokeWidth="2.5"
                    strokeLinecap="round"
                  />
                  <path
                    d="M10.3 4.7 3.6 16.3a2 2 0 0 0 1.7 3h13.4a2 2 0 0 0 1.7-3L13.7 4.7a2 2 0 0 0-3.4 0Z"
                    stroke="currentColor"
                    strokeWidth="1.7"
                    strokeLinejoin="round"
                  />
                </svg>
              </div>

              <h1 className="text-2xl font-bold tracking-[-0.03em] text-[#191721] sm:text-3xl">
                Нужно снова ввести номер
              </h1>

              <p className="mt-3 max-w-2xl text-[15px] leading-7 text-[#777580]">
                Временный безопасный доступ закончился или не был
                открыт в этом браузере.
              </p>

              <Link
                className="mt-6 inline-flex min-h-11 items-center justify-center rounded-[14px] bg-gradient-to-r from-[#6b5af5] to-[#7664f8] px-5 py-2.5 font-semibold text-white shadow-[0_10px_25px_rgba(105,86,238,.20)] transition-all hover:-translate-y-0.5"
                href="/appeal/check"
              >
                Перейти к проверке обращения
              </Link>
            </div>
          </div>
        ) : null}

        {appeal ? (
          <>
            {/* STATUS */}
            <div className="surface-card relative overflow-hidden rounded-[28px] p-6 shadow-[0_20px_60px_rgba(68,53,126,.08)] sm:p-9">
              <div
                aria-hidden="true"
                className="pointer-events-none absolute -right-24 -top-24 h-64 w-64 rounded-full bg-violet-300/15 blur-3xl"
              />

              <div className="relative">
                <div className="mb-5 flex items-center gap-2">
                  <span className="h-2 w-2 rounded-full bg-[#6b5af5] shadow-[0_0_0_5px_rgba(107,90,245,.10)]" />
                  <p className="page-eyebrow !mb-0">
                    Текущий статус
                  </p>
                </div>

                <div className="flex flex-wrap items-center gap-3">
                  <StatusBadge value={appeal.status} />

                  {appeal.category ? (
                    <span className="break-safe rounded-full border border-[#e7e3f1] bg-[#faf9fc] px-3 py-1.5 text-sm text-[#686471]">
                      Тема: {appeal.category.name}
                    </span>
                  ) : null}
                </div>

                <h1 className="break-safe mt-5 text-2xl font-bold tracking-[-0.03em] text-[#191721] sm:text-3xl">
                  {appeal.status_text}
                </h1>

                <p className="mt-3 text-xs text-[#9995a0]">
                  Обновлено{" "}
                  {new Date(appeal.updated_at).toLocaleString(
                    "ru-RU",
                  )}
                </p>

                {appeal.rejection_reason ? (
                  <div className="break-safe mt-5 rounded-[17px] border border-[#e8e5ef] bg-[#f8f7fa] p-4 text-sm leading-6 text-[#5f5b66]">
                    {appeal.rejection_reason}
                  </div>
                ) : null}
              </div>
            </div>

            {/* TIMELINE */}
            <div className="surface-card rounded-[26px] p-6 shadow-[0_20px_60px_rgba(68,53,126,.06)] sm:p-8">
              <div className="flex items-center justify-between gap-4">
                <div>
                  <h2 className="text-xl font-bold tracking-tight text-[#191721]">
                    История статуса
                  </h2>

                  <p className="mt-1 text-sm text-[#9995a0]">
                    Как менялось обращение
                  </p>
                </div>

                <div className="hidden h-10 w-10 items-center justify-center rounded-[13px] bg-[#eeeaff] text-[#6754f7] sm:flex">
                  <svg
                    width="19"
                    height="19"
                    viewBox="0 0 24 24"
                    fill="none"
                    aria-hidden="true"
                  >
                    <path
                      d="M12 6v6l4 2"
                      stroke="currentColor"
                      strokeWidth="1.8"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    />
                    <circle
                      cx="12"
                      cy="12"
                      r="8.5"
                      stroke="currentColor"
                      strokeWidth="1.8"
                    />
                  </svg>
                </div>
              </div>

              <ol className="mt-7 space-y-0">
                {appeal.timeline.map((item, index) => (
                  <li
                    key={`${item.status}-${item.occurred_at}`}
                    className="relative flex gap-4 pb-7 last:pb-0"
                  >
                    {index < appeal.timeline.length - 1 ? (
                      <span className="absolute left-[15px] top-8 h-[calc(100%-8px)] w-px bg-gradient-to-b from-[#d8d2ff] to-[#eeeaf4]" />
                    ) : null}

                    <span className="relative z-10 flex size-8 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-[#6b5af5] to-[#7968f8] text-sm font-bold text-white shadow-[0_5px_14px_rgba(105,86,238,.18)]">
                      {index + 1}
                    </span>

                    <div className="min-w-0 pt-0.5">
                      <p className="text-[15px] font-semibold leading-6 text-[#302d39]">
                        {item.text}
                      </p>

                      <p className="mt-1 text-xs text-[#9995a0]">
                        {new Date(
                          item.occurred_at,
                        ).toLocaleString("ru-RU")}
                      </p>
                    </div>
                  </li>
                ))}
              </ol>
            </div>

            {/* CRISIS */}
            {appeal.show_crisis_support ? (
              <CrisisPanel
                resources={appeal.crisis_support_resources}
              />
            ) : null}

            {/* DIALOG */}
            {messages.length ||
            [
              "in_progress",
              "needs_clarification",
              "answer_ready",
            ].includes(appeal.status) ? (
              <section className="surface-card rounded-[26px] p-6 shadow-[0_20px_60px_rgba(68,53,126,.06)] sm:p-8">
                <div className="flex flex-wrap items-start justify-between gap-4">
                  <div>
                    <h2 className="text-xl font-bold tracking-tight text-[#191721]">
                      Диалог со специалистом
                    </h2>

                    <p className="mt-1 text-sm text-[#9995a0]">
                      Здесь можно безопасно продолжить разговор
                    </p>
                  </div>

                  <span className="inline-flex items-center gap-1.5 rounded-full border border-[#e1dcff] bg-[#f4f1ff] px-3 py-1.5 text-xs font-semibold text-[#6754f7]">
                    <span className="h-1.5 w-1.5 rounded-full bg-[#6b5af5]" />
                    Конфиденциально
                  </span>
                </div>

                <div className="my-6 space-y-3">
                  {messages.map((item) => (
                    <div
                      key={item.id}
                      className={`break-safe max-w-[92%] rounded-[19px] border p-4 text-[15px] leading-7 shadow-[0_5px_20px_rgba(40,30,80,.03)] ${
                        item.author_type === "applicant"
                          ? "ml-auto border-[#dcd7ff] bg-gradient-to-br from-[#f3f0ff] to-[#faf9ff]"
                          : "mr-auto border-[#e9e6ee] bg-white"
                      }`}
                    >
                      <p className="mb-1.5 text-xs font-semibold text-[#9995a0]">
                        {item.author_label}
                      </p>

                      <p className="whitespace-pre-wrap text-[#393642]">
                        {item.body}
                      </p>
                    </div>
                  ))}
                </div>

                {[
                  "in_progress",
                  "needs_clarification",
                ].includes(appeal.status) ? (
                  <>
                    <Textarea
                      className="min-h-32 resize-y rounded-[17px] border-[#e5e2ec] bg-white/80 p-4 shadow-none placeholder:text-[#aaa7b1] focus:border-[#7564f8] focus:ring-4 focus:ring-[#7564f8]/10"
                      value={message}
                      onChange={(event) =>
                        setMessage(event.target.value)
                      }
                      maxLength={5000}
                      placeholder="Напишите специалисту"
                    />

                    <Button
                      className="mt-3 h-11 rounded-[14px] border-0 bg-gradient-to-r from-[#6b5af5] to-[#7664f8] px-5 font-semibold text-white shadow-[0_10px_25px_rgba(105,86,238,.18)] hover:from-[#604eeb] hover:to-[#6d5af0] disabled:opacity-50"
                      size="lg"
                      disabled={busy || !message.trim()}
                      onClick={() =>
                        void act(
                          () =>
                            publicAppealsApi.sendMessage(
                              message,
                            ),
                          "Сообщение отправлено.",
                        ).then(() => setMessage(""))
                      }
                    >
                      Отправить сообщение
                    </Button>
                  </>
                ) : null}
              </section>
            ) : null}

            {/* ANSWER READY */}
            {appeal.status === "answer_ready" ? (
              <section className="relative overflow-hidden rounded-[26px] border border-[#dcd7ff] bg-gradient-to-br from-[#f3f0ff] via-[#faf9ff] to-[#f3fbff] p-6 shadow-[0_20px_60px_rgba(103,84,247,.09)] sm:p-8">
                <div
                  aria-hidden="true"
                  className="pointer-events-none absolute -right-20 -top-20 h-48 w-48 rounded-full bg-violet-300/20 blur-3xl"
                />

                <div className="relative">
                  <div className="mb-5 flex items-center gap-3">
                    <div className="flex h-10 w-10 items-center justify-center rounded-[13px] bg-white text-[#6754f7] shadow-sm">
                      ✓
                    </div>

                    <div>
                      <h2 className="font-bold tracking-tight text-[#191721]">
                        Помогли ли рекомендации?
                      </h2>

                      <p className="text-sm text-[#8d8995]">
                        Ваш ответ поможет завершить обращение
                      </p>
                    </div>
                  </div>

                  <div className="flex flex-col gap-3">
                    <Button
                      className="h-11 rounded-[14px] border-0 bg-gradient-to-r from-[#6b5af5] to-[#7664f8] font-semibold text-white shadow-[0_10px_25px_rgba(105,86,238,.18)] hover:from-[#604eeb] hover:to-[#6d5af0]"
                      disabled={busy}
                      onClick={() =>
                        void act(
                          () =>
                            publicAppealsApi.resolve(
                              "helped",
                            ),
                          "Спасибо! Обращение завершено.",
                        )
                      }
                    >
                      Это помогло
                    </Button>

                    <Textarea
                      value={returnExplanation}
                      onChange={(event) =>
                        setReturnExplanation(
                          event.target.value,
                        )
                      }
                      maxLength={2000}
                      placeholder="Если не помогло, расскажите, чего не хватило"
                      className="min-h-28 rounded-[17px] border-[#e5e2ec] bg-white/80 p-4 shadow-none placeholder:text-[#aaa7b1] focus:border-[#7564f8] focus:ring-4 focus:ring-[#7564f8]/10"
                    />

                    <Button
                      variant="outline"
                      disabled={
                        busy ||
                        !returnExplanation.trim() ||
                        appeal.return_count >=
                          appeal.max_returns
                      }
                      onClick={() =>
                        void act(
                          () =>
                            publicAppealsApi.resolve(
                              "not_helped",
                              returnExplanation,
                            ),
                          "Обращение возвращено оператору.",
                        )
                      }
                      className="h-11 rounded-[14px] border-[#ddd8ef] bg-white/80 font-semibold text-[#413d4c] hover:bg-white"
                    >
                      Это не помогло
                    </Button>
                  </div>

                  {appeal.return_count >= appeal.max_returns ? (
                    <p className="mt-3 text-sm leading-6 text-[#777580]">
                      Лимит возвратов исчерпан. Вы всё ещё
                      можете оставить жалобу.
                    </p>
                  ) : null}
                </div>
              </section>
            ) : null}

            {/* FEEDBACK */}
            {["completed", "returned"].includes(
              appeal.status,
            ) ? (
              <section className="surface-card space-y-4 rounded-[26px] p-6 shadow-[0_20px_60px_rgba(68,53,126,.06)] sm:p-8">
                <div>
                  <h2 className="text-xl font-bold tracking-tight text-[#191721]">
                    Оценка помощи
                  </h2>

                  <p className="mt-1 text-sm text-[#9995a0]">
                    Это необязательно
                  </p>
                </div>

                <select
                  aria-label="Оценка"
                  value={rating}
                  onChange={(event) =>
                    setRating(Number(event.target.value))
                  }
                  className="h-12 w-full rounded-[15px] border border-[#e5e2ec] bg-white/80 px-4 text-sm text-[#393642] outline-none transition-all focus:border-[#7564f8] focus:ring-4 focus:ring-[#7564f8]/10 sm:w-auto"
                >
                  {[5, 4, 3, 2, 1].map((value) => (
                    <option key={value} value={value}>
                      {value} из 5
                    </option>
                  ))}
                </select>

                <Textarea
                  value={feedback}
                  onChange={(event) =>
                    setFeedback(event.target.value)
                  }
                  maxLength={2000}
                  placeholder="Комментарий — необязательно"
                  className="min-h-28 rounded-[17px] border-[#e5e2ec] bg-white/80 p-4 shadow-none placeholder:text-[#aaa7b1] focus:border-[#7564f8] focus:ring-4 focus:ring-[#7564f8]/10"
                />

                <Button
                  variant="outline"
                  disabled={busy}
                  onClick={() =>
                    void act(
                      () =>
                        publicAppealsApi.feedback(
                          rating,
                          feedback,
                        ),
                      "Спасибо за обратную связь.",
                    )
                  }
                  className="h-11 rounded-[14px] border-[#ddd8ef] bg-white/80 font-semibold text-[#413d4c] hover:bg-[#f8f6ff]"
                >
                  Отправить оценку
                </Button>
              </section>
            ) : null}

            {/* COMPLAINT */}
            <details className="surface-card group rounded-[26px] p-6 shadow-[0_20px_60px_rgba(68,53,126,.05)] sm:p-7">
              <summary className="cursor-pointer list-none rounded-md font-semibold text-[#302d39] outline-none focus-visible:ring-2 focus-visible:ring-[#7564f8]/30 focus-visible:ring-offset-4">
                <span className="flex items-center justify-between gap-4">
                  <span>Пожаловаться на работу сервиса</span>

                  <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-[#f3f1f7] text-[#77727f] transition-transform group-open:rotate-45">
                    +
                  </span>
                </span>
              </summary>

              <div className="mt-5 space-y-3 border-t border-[#efedf3] pt-5">
                <p className="text-sm leading-6 text-[#777580]">
                  Жалоба не будет показана специалисту.
                </p>

                <Textarea
                  value={complaint}
                  onChange={(event) =>
                    setComplaint(event.target.value)
                  }
                  maxLength={3000}
                  className="min-h-28 rounded-[17px] border-[#e5e2ec] bg-white/80 p-4 shadow-none focus:border-[#7564f8] focus:ring-4 focus:ring-[#7564f8]/10"
                />

                <Button
                  variant="outline"
                  disabled={busy || !complaint.trim()}
                  onClick={() =>
                    void act(
                      () =>
                        publicAppealsApi.complaint(
                          complaint,
                        ),
                      "Жалоба принята.",
                    ).then(() => setComplaint(""))
                  }
                  className="h-11 rounded-[14px] border-[#ddd8ef] bg-white/80 font-semibold text-[#413d4c] hover:bg-[#f8f6ff]"
                >
                  Отправить жалобу
                </Button>
              </div>
            </details>

            {/* NOTICE */}
            {notice ? (
              <p
                className="rounded-[18px] border border-[#ddd8f2] bg-white/80 p-4 text-sm leading-6 text-[#514d5b] shadow-[0_10px_30px_rgba(68,53,126,.05)]"
                role="status"
              >
                {notice}
              </p>
            ) : null}

            {/* LEAVE */}
            <Button
              type="button"
              variant="outline"
              className="h-12 w-full rounded-[15px] border-[#ddd8ef] bg-white/70 font-semibold text-[#575260] hover:bg-[#f8f6ff]"
              onClick={leave}
            >
              Закрыть доступ на этом устройстве
            </Button>
          </>
        ) : null}
      </section>
    </PublicShell>
  )
}