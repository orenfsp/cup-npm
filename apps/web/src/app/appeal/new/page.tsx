"use client"

import { useEffect, useMemo, useState } from "react"
import Link from "next/link"

import { CrisisPanel } from "@/components/appeals/crisis-panel"
import { PublicShell } from "@/components/appeals/public-shell"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import {
  type ApplicantType,
  type CreatedAppeal,
  type PublicReference,
  publicAppealsApi,
} from "@/lib/appeals"

type PathChoice = "category" | "words"
type AnswerValue = string | boolean | string[]

export default function NewAppealPage() {
  const [reference, setReference] = useState<PublicReference | null>(null)
  const [applicantType, setApplicantType] = useState<ApplicantType>("student")
  const [pathChoice, setPathChoice] = useState<PathChoice>("category")
  const [categoryId, setCategoryId] = useState("")
  const [description, setDescription] = useState("")
  const [answers, setAnswers] = useState<Record<string, AnswerValue>>({})
  const [files, setFiles] = useState<File[]>([])
  const [failedFiles, setFailedFiles] = useState<File[]>([])
  const [created, setCreated] = useState<CreatedAppeal | null>(null)
  const [error, setError] = useState("")
  const [busy, setBusy] = useState(false)
  const [contact, setContact] = useState("")
  const [contactSaved, setContactSaved] = useState(false)

  useEffect(() => {
    const controller = new AbortController()

    publicAppealsApi
      .reference(controller.signal)
      .then((result) => {
        setReference(result)

        if (result.applicant_types.length) {
          setApplicantType(result.applicant_types[0].code)
        }
      })
      .catch(() =>
        setError("Не удалось загрузить форму. Попробуйте обновить страницу."),
      )

    return () => controller.abort()
  }, [])

  const formal =
    reference?.applicant_types.find(
      (item) => item.code === applicantType,
    )?.tone !== "informal"

  const selectedCategory = useMemo(
    () =>
      reference?.categories.find(
        (category) => category.id === categoryId,
      ),
    [categoryId, reference],
  )

  const descriptionRequired =
    pathChoice === "words" || selectedCategory?.requires_description

  function selectFiles(list: FileList | null) {
    if (!list) return

    const selected = Array.from(list).slice(0, 5)

    if (Array.from(list).length > 5) {
      setError("Можно приложить не больше пяти изображений.")
    } else {
      setError("")
    }

    setFiles(selected)
  }

  async function uploadFiles(selectedFiles: File[]) {
    const failures: File[] = []

    for (const file of selectedFiles) {
      try {
        await publicAppealsApi.uploadAttachment(file)
      } catch {
        failures.push(file)
      }
    }

    setFailedFiles(failures)
  }

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError("")

    if (files.some((file) => file.size > 10 * 1024 * 1024)) {
      setError("Каждое изображение должно быть не больше 10 МБ.")
      return
    }

    setBusy(true)

    try {
      const nonemptyAnswers = Object.fromEntries(
        Object.entries(answers).filter(([, value]) =>
          Array.isArray(value)
            ? value.length > 0
            : typeof value === "string"
              ? value.trim()
              : true,
        ),
      )

      const result = await publicAppealsApi.create({
        applicant_type: applicantType,
        category_id: categoryId || null,
        description: description.trim() || null,
        intake_answers:
          Object.keys(nonemptyAnswers).length ? nonemptyAnswers : null,
      })

      setCreated(result)
      await uploadFiles(files)
    } catch {
      setError(
        "Не удалось отправить обращение. Проверьте форму и попробуйте ещё раз.",
      )
    } finally {
      setBusy(false)
    }
  }

  async function copyTrack() {
    if (created) {
      await navigator.clipboard.writeText(created.track_number)
    }
  }

  function saveTrack() {
    if (!created) return

    const blob = new Blob(
      [
        `Номер обращения в Отклик: ${created.track_number}\n\nНе передавайте его посторонним.`,
      ],
      { type: "text/plain;charset=utf-8" },
    )

    const url = URL.createObjectURL(blob)
    const anchor = document.createElement("a")

    anchor.href = url
    anchor.download = "otklik-track-number.txt"
    anchor.click()

    URL.revokeObjectURL(url)
  }

  async function saveContact() {
    if (!contact.trim()) return

    setContactSaved(false)

    try {
      await publicAppealsApi.saveCrisisContact(contact.trim())
      setContact("")
      setContactSaved(true)
    } catch {
      setError(
        "Не удалось сохранить контакт. Обращение уже принято — попробуйте ещё раз позже.",
      )
    }
  }

  if (created) {
    return (
      <PublicShell>
        <section className="mx-auto w-full max-w-2xl space-y-6 py-8 sm:py-14">
          {/* SUCCESS CARD */}
          <div className="surface-card relative overflow-hidden rounded-[28px] p-6 sm:p-10">
            <div
              aria-hidden="true"
              className="pointer-events-none absolute -right-24 -top-24 h-56 w-56 rounded-full bg-violet-300/20 blur-3xl"
            />

            <div className="relative">
              <div className="mb-5 flex items-center gap-2">
                <span className="flex h-8 w-8 items-center justify-center rounded-full bg-[#ece9ff] text-sm font-bold text-[#6754f7]">
                  ✓
                </span>

                <p className="page-eyebrow !mb-0">
                  Обращение принято
                </p>
              </div>

              <h1 className="text-3xl font-bold tracking-[-0.03em] text-[#15131d] sm:text-[34px]">
                Сохраните этот номер
              </h1>

              <p className="mt-3 text-[15px] leading-7 text-[#777580]">
                Сервис не сможет восстановить номер. Он не сохранён в
                браузере и не находится в адресе страницы.
              </p>

              <div className="my-7 rounded-[22px] border border-[#dcd7ff] bg-gradient-to-br from-[#f3f0ff] to-[#f7fbff] p-5 text-center shadow-inner sm:p-7">
                <p className="mb-2 text-xs font-semibold uppercase tracking-[0.16em] text-[#8b84a4]">
                  Номер обращения
                </p>

                <div className="break-safe font-mono text-2xl font-bold tracking-[0.12em] text-[#4f42b7] sm:text-4xl">
                  {created.track_number}
                </div>
              </div>

              <div className="grid gap-3 sm:grid-cols-2">
                <Button
                  type="button"
                  size="lg"
                  onClick={copyTrack}
                  className="h-12 rounded-[15px] border-0 bg-gradient-to-r from-[#6b5af5] to-[#7664f8] font-semibold text-white shadow-[0_12px_28px_rgba(105,86,238,.22)] hover:from-[#604eeb] hover:to-[#6d5af0]"
                >
                  Копировать
                </Button>

                <Button
                  type="button"
                  size="lg"
                  variant="outline"
                  onClick={saveTrack}
                  className="h-12 rounded-[15px] border-[#e2def5] bg-white/70 font-semibold text-[#373344] hover:bg-[#f5f2ff]"
                >
                  Сохранить файлом
                </Button>
              </div>
            </div>
          </div>

          {/* FAILED FILES */}
          {failedFiles.length ? (
            <div className="rounded-[24px] border border-rose-200/80 bg-rose-50/80 p-5 text-sm text-rose-950 shadow-[0_12px_40px_rgba(190,24,93,.06)] sm:p-6">
              <div className="flex gap-3">
                <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-white text-rose-600 shadow-sm">
                  !
                </span>

                <div>
                  <p className="font-semibold">
                    Обращение принято, но не все файлы загрузились.
                  </p>

                  <p className="mt-1 leading-6 text-rose-800/80">
                    {failedFiles.map((file) => file.name).join(", ")}
                  </p>
                </div>
              </div>

              <Button
                className="mt-4 rounded-[13px] border-rose-200 bg-white text-rose-800 hover:bg-rose-50"
                variant="outline"
                disabled={busy}
                onClick={async () => {
                  setBusy(true)
                  await uploadFiles(failedFiles)
                  setBusy(false)
                }}
              >
                Повторить загрузку
              </Button>
            </div>
          ) : null}

          {/* CRISIS SUPPORT */}
          {created.show_crisis_support ? (
            <>
              <CrisisPanel
                resources={created.crisis_support_resources}
              />

              <div className="surface-card rounded-[26px] p-6 sm:p-8">
                <div className="mb-5 flex items-start gap-3">
                  <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-[13px] bg-[#ece9ff] text-[#6754f7]">
                    <svg
                      width="19"
                      height="19"
                      viewBox="0 0 24 24"
                      fill="none"
                      aria-hidden="true"
                    >
                      <path
                        d="M20 11.5a8.4 8.4 0 0 1-8 8.5 8.7 8.7 0 0 1-4.1-1l-3.9 1 1.1-3.5A8.5 8.5 0 1 1 20 11.5Z"
                        stroke="currentColor"
                        strokeWidth="1.7"
                      />
                    </svg>
                  </div>

                  <div>
                    <h2 className="text-lg font-bold tracking-tight text-[#191721]">
                      Оставить контакт для экстренной связи
                    </h2>

                    <p className="mt-1 text-sm text-[#96929d]">
                      Необязательно
                    </p>
                  </div>
                </div>

                <p className="text-[15px] leading-7 text-[#777580]">
                  Контакт будет зашифрован и сохранён отдельно. Это
                  уменьшает анонимность. Можно ничего не указывать —
                  обращение уже принято.
                </p>

                <Input
                  value={contact}
                  maxLength={1000}
                  onChange={(event) => setContact(event.target.value)}
                  placeholder="Контакт, только если вы этого хотите"
                  className="mt-5 h-12 rounded-[15px] border-[#e5e2ec] bg-white/80 px-4 shadow-none focus:border-[#7564f8] focus:ring-4 focus:ring-[#7564f8]/10"
                />

                <Button
                  type="button"
                  variant="outline"
                  onClick={saveContact}
                  className="mt-3 h-11 rounded-[14px] border-[#e2def5] bg-white font-semibold text-[#373344] hover:bg-[#f5f2ff]"
                >
                  Сохранить контакт
                </Button>

                {contactSaved ? (
                  <p className="mt-3 text-sm font-medium text-[#6754f7]">
                    ✓ Контакт сохранён.
                  </p>
                ) : null}
              </div>
            </>
          ) : null}

          {error ? (
            <p
              className="state-error rounded-[18px]"
              role="alert"
            >
              {error}
            </p>
          ) : null}

          <Link
            href="/appeal/current"
            className="flex min-h-12 items-center justify-center rounded-[15px] bg-gradient-to-r from-[#6b5af5] to-[#7664f8] px-5 py-3 text-center font-semibold text-white shadow-[0_12px_28px_rgba(105,86,238,.20)] transition-all hover:-translate-y-0.5 hover:shadow-[0_16px_34px_rgba(105,86,238,.26)]"
          >
            Посмотреть статус
          </Link>
        </section>
      </PublicShell>
    )
  }

  return (
    <PublicShell>
      <form
        onSubmit={submit}
        className="mx-auto w-full max-w-3xl space-y-6 py-8 sm:space-y-7 sm:py-14"
      >
        {/* PAGE HEADER */}
        <div className="relative overflow-hidden rounded-[28px] border border-white/80 bg-white/65 p-6 shadow-[0_20px_60px_rgba(68,53,126,.07)] backdrop-blur-xl sm:p-8">
          <div
            aria-hidden="true"
            className="pointer-events-none absolute -right-20 -top-24 h-64 w-64 rounded-full bg-violet-300/15 blur-3xl"
          />

          <div className="relative">
            <p className="page-eyebrow">Новое обращение</p>

            <h1 className="mt-2 text-3xl font-bold tracking-[-0.035em] text-[#15131d] sm:text-[36px]">
              Расскажите, что произошло
            </h1>

            <p className="mt-3 max-w-2xl text-[15px] leading-7 text-[#777580] sm:text-base">
              Можно выбрать тему или рассказать своими словами.
              Не торопитесь — расскажите столько, сколько считаете
              нужным.
            </p>
          </div>
        </div>

        {/* APPLICANT TYPE */}
        <fieldset className="surface-card space-y-5 rounded-[26px] p-5 sm:p-8">
          <legend className="px-1 text-lg font-bold tracking-tight text-[#191721]">
            Кто обращается?
          </legend>

          <div className="grid gap-3 sm:grid-cols-3">
            {reference?.applicant_types.map((item) => (
              <button
                key={item.code}
                type="button"
                aria-pressed={applicantType === item.code}
                className={`group flex min-h-24 flex-col items-center justify-center rounded-[18px] border px-4 py-4 text-base font-semibold transition-all duration-200 ${
                  applicantType === item.code
                    ? "border-[#6b5af5] bg-gradient-to-br from-[#6b5af5] to-[#7867f8] text-white shadow-[0_12px_30px_rgba(105,86,238,.22)]"
                    : "border-[#e8e5ef] bg-white/70 text-[#302d39] hover:-translate-y-0.5 hover:border-[#cfc8ff] hover:bg-[#f8f6ff]"
                }`}
                onClick={() => setApplicantType(item.code)}
              >
                {item.label}

                {applicantType === item.code ? (
                  <span className="mt-1.5 text-xs font-semibold text-violet-100">
                    ✓ Выбрано
                  </span>
                ) : null}
              </button>
            ))}
          </div>
        </fieldset>

        {/* PATH */}
        <section className="surface-card space-y-5 rounded-[26px] p-5 sm:p-8">
          <div>
            <h2 className="text-lg font-bold tracking-tight text-[#191721]">
              Как удобнее рассказать?
            </h2>

            <p className="mt-1 text-sm text-[#96929d]">
              Выберите способ, который кажется комфортнее.
            </p>
          </div>

          <div className="grid gap-3 sm:grid-cols-2">
            {(
              [
                [
                  "category",
                  "Выбрать ситуацию",
                  "Подойдёт, если тему легко определить",
                ],
                [
                  "words",
                  "Рассказать своими словами",
                  "Можно начать сразу со свободного текста",
                ],
              ] as const
            ).map(([value, title, text]) => (
              <button
                key={value}
                type="button"
                aria-pressed={pathChoice === value}
                className={`relative min-h-28 rounded-[19px] border p-5 text-left transition-all duration-200 ${
                  pathChoice === value
                    ? "border-[#cfc8ff] bg-[#f5f2ff] shadow-[0_10px_30px_rgba(103,84,247,.08)] ring-1 ring-[#dcd7ff]"
                    : "border-[#e8e5ef] bg-white/65 hover:-translate-y-0.5 hover:border-[#d8d2f7] hover:bg-white"
                }`}
                onClick={() => setPathChoice(value)}
              >
                {pathChoice === value ? (
                  <span className="absolute right-4 top-4 flex h-6 w-6 items-center justify-center rounded-full bg-[#6b5af5] text-xs font-bold text-white">
                    ✓
                  </span>
                ) : null}

                <span className="font-semibold text-[#27232f]">
                  {title}
                </span>

                <span className="mt-1.5 block max-w-[250px] text-sm leading-5 text-[#88848f]">
                  {text}
                </span>

                {pathChoice === value ? (
                  <span className="mt-3 block text-xs font-semibold text-[#6754f7]">
                    Выбрано
                  </span>
                ) : null}
              </button>
            ))}
          </div>

          {/* CATEGORIES */}
          {pathChoice === "category" ? (
            <div className="grid gap-2.5 sm:grid-cols-2">
              {reference?.categories.map((category) => (
                <button
                  key={category.id}
                  type="button"
                  aria-pressed={categoryId === category.id}
                  className={`min-h-16 rounded-[16px] border p-4 text-left text-[15px] font-semibold transition-all duration-200 ${
                    categoryId === category.id
                      ? "border-[#6b5af5] bg-gradient-to-r from-[#6b5af5] to-[#7867f8] text-white shadow-[0_10px_25px_rgba(105,86,238,.18)]"
                      : "border-[#e8e5ef] bg-white/70 text-[#302d39] hover:border-[#cfc8ff] hover:bg-[#f8f6ff]"
                  }`}
                  onClick={() => {
                    setCategoryId(category.id)

                    if (category.requires_description) {
                      setPathChoice("words")
                    }
                  }}
                >
                  {category.name}
                </button>
              ))}
            </div>
          ) : null}

          {/* DESCRIPTION */}
          {(pathChoice === "words" || categoryId) && (
            <div className="space-y-2.5">
              <Label
                htmlFor="description"
                className="text-[13px] font-semibold text-[#393542]"
              >
                Опишите ситуацию{" "}
                {descriptionRequired ? "" : "(необязательно)"}
              </Label>

              <Textarea
                id="description"
                rows={7}
                maxLength={5000}
                required={Boolean(descriptionRequired)}
                value={description}
                onChange={(event) => setDescription(event.target.value)}
                placeholder={
                  formal
                    ? "Расскажите столько, сколько считаете нужным"
                    : "Расскажи столько, сколько считаешь нужным"
                }
                className="min-h-[170px] resize-y rounded-[17px] border-[#e5e2ec] bg-white/80 p-4 leading-6 shadow-none placeholder:text-[#aaa7b1] focus:border-[#7564f8] focus:ring-4 focus:ring-[#7564f8]/10"
              />
            </div>
          )}
        </section>

        {/* QUESTIONS */}
        <section className="surface-card space-y-6 rounded-[26px] p-5 sm:p-8">
          <div>
            <h2 className="text-lg font-bold tracking-tight text-[#191721]">
              Несколько уточнений
            </h2>

            <p className="mt-1 text-[14px] text-[#96929d]">
              Ответы необязательны.
            </p>
          </div>

          {reference?.intake_questions
            .filter(
              (question) =>
                !categoryId ||
                question.category_ids.includes(categoryId),
            )
            .map((question) => {
              const required =
                question.required ||
                question.required_category_ids.includes(categoryId)

              const value = answers[question.id]

              return (
                <div
                  key={question.id}
                  className="space-y-2.5 border-t border-[#efedf3] pt-5 first:border-t-0 first:pt-0"
                >
                  <Label
                    htmlFor={question.id}
                    className="text-[13px] font-semibold text-[#393542]"
                  >
                    {question.label} {required ? "*" : ""}
                  </Label>

                  {question.help_text ? (
                    <p className="text-sm leading-6 text-[#96929d]">
                      {question.help_text}
                    </p>
                  ) : null}

                  {question.field_type === "long_text" ? (
                    <Textarea
                      id={question.id}
                      required={required}
                      maxLength={question.max_length}
                      value={
                        typeof value === "string" ? value : ""
                      }
                      onChange={(event) =>
                        setAnswers((current) => ({
                          ...current,
                          [question.id]: event.target.value,
                        }))
                      }
                      className="min-h-[120px] rounded-[16px] border-[#e5e2ec] bg-white/80 p-4 shadow-none focus:border-[#7564f8] focus:ring-4 focus:ring-[#7564f8]/10"
                    />
                  ) : question.field_type === "single_choice" ? (
                    <select
                      id={question.id}
                      required={required}
                      className="h-12 w-full rounded-[15px] border border-[#e5e2ec] bg-white/80 px-4 text-sm text-[#302d39] outline-none transition-all focus:border-[#7564f8] focus:ring-4 focus:ring-[#7564f8]/10"
                      value={
                        typeof value === "string" ? value : ""
                      }
                      onChange={(event) =>
                        setAnswers((current) => ({
                          ...current,
                          [question.id]: event.target.value,
                        }))
                      }
                    >
                      <option value="">Выберите вариант</option>

                      {question.options.map((option) => (
                        <option key={option}>{option}</option>
                      ))}
                    </select>
                  ) : question.field_type === "multi_choice" ? (
                    <div className="space-y-2">
                      {question.options.map((option) => {
                        const selected = Array.isArray(value)
                          ? value
                          : []

                        return (
                          <label
                            key={option}
                            className="flex cursor-pointer items-center gap-3 rounded-[15px] border border-[#e8e5ef] bg-white/65 px-4 py-3 text-sm text-[#393542] transition-colors hover:border-[#d5cff5] hover:bg-[#f8f6ff]"
                          >
                            <Checkbox
                              checked={selected.includes(option)}
                              onCheckedChange={(checked) =>
                                setAnswers((current) => ({
                                  ...current,
                                  [question.id]:
                                    checked
                                      ? [
                                          ...selected,
                                          option,
                                        ]
                                      : selected.filter(
                                          (item) =>
                                            item !== option,
                                        ),
                                }))
                              }
                            />

                            {option}
                          </label>
                        )
                      })}
                    </div>
                  ) : question.field_type === "boolean" ? (
                    <label className="flex cursor-pointer items-center gap-3 rounded-[15px] border border-[#e8e5ef] bg-white/65 px-4 py-3 text-sm text-[#393542] transition-colors hover:border-[#d5cff5] hover:bg-[#f8f6ff]">
                      <Checkbox
                        checked={value === true}
                        onCheckedChange={(checked) =>
                          setAnswers((current) => ({
                            ...current,
                            [question.id]: checked === true,
                          }))
                        }
                      />

                      Да
                    </label>
                  ) : (
                    <Input
                      id={question.id}
                      required={required}
                      maxLength={question.max_length}
                      value={
                        typeof value === "string" ? value : ""
                      }
                      onChange={(event) =>
                        setAnswers((current) => ({
                          ...current,
                          [question.id]: event.target.value,
                        }))
                      }
                      className="h-12 rounded-[15px] border-[#e5e2ec] bg-white/80 px-4 shadow-none focus:border-[#7564f8] focus:ring-4 focus:ring-[#7564f8]/10"
                    />
                  )}
                </div>
              )
            })}
        </section>

        {/* ATTACHMENTS */}
        <section className="surface-card space-y-4 rounded-[26px] p-5 sm:p-8">
          <div>
            <Label
              className="text-base font-bold text-[#191721]"
              htmlFor="attachments"
            >
              Скриншоты или изображения
            </Label>

            <p className="mt-1 text-sm text-[#96929d]">
              Необязательно
            </p>
          </div>

          <Input
            id="attachments"
            type="file"
            accept="image/jpeg,image/png,image/webp"
            multiple
            onChange={(event) =>
              selectFiles(event.target.files)
            }
            className="h-auto min-h-12 cursor-pointer rounded-[15px] border-[#e5e2ec] bg-white/80 px-3 py-2 text-sm file:mr-3 file:rounded-[10px] file:border-0 file:bg-[#eeeaff] file:px-3 file:py-2 file:font-semibold file:text-[#6754f7] hover:border-[#d4cdf5]"
          />

          <p className="text-xs leading-5 text-[#96929d]">
            JPEG, PNG или WEBP; до 5 файлов и до 10 МБ каждый.
            Метаданные будут удалены.
          </p>

          {files.length ? (
            <div className="grid gap-2">
              {files.map((file, index) => (
                <div
                  key={`${file.name}-${index}`}
                  className="break-safe flex items-center justify-between gap-3 rounded-[14px] border border-[#e8e5ef] bg-white/65 px-4 py-3 text-sm"
                >
                  <span className="min-w-0 truncate font-medium text-[#393542]">
                    Изображение {index + 1}
                  </span>

                  <span className="shrink-0 text-[#96929d]">
                    {Math.ceil(file.size / 1024)} КБ
                  </span>
                </div>
              ))}
            </div>
          ) : null}
        </section>

        {/* ERROR */}
        {error ? (
          <p
            className="state-error rounded-[18px]"
            role="alert"
          >
            {error}
          </p>
        ) : null}

        {/* SUBMIT */}
        <Button
          className="h-13 w-full rounded-[16px] border-0 bg-gradient-to-r from-[#6b5af5] via-[#715ff7] to-[#58cde7] text-base font-bold text-white shadow-[0_16px_38px_rgba(105,86,238,.22)] transition-all duration-200 hover:-translate-y-0.5 hover:shadow-[0_20px_45px_rgba(105,86,238,.28)] disabled:translate-y-0 disabled:opacity-60"
          type="submit"
          disabled={busy || !reference}
        >
          {busy ? "Отправляем…" : "Отправить обращение"}
        </Button>

        <div className="mx-auto flex max-w-2xl items-start gap-2.5 px-2 text-center text-xs leading-5 text-[#96929d]">
          <svg
            className="mt-0.5 hidden shrink-0 text-[#8a80d8] sm:block"
            width="15"
            height="15"
            viewBox="0 0 24 24"
            fill="none"
            aria-hidden="true"
          >
            <path
              d="M12 3l7 4v5c0 4.5-3 7.5-7 9-4-1.5-7-4.5-7-9V7l7-4z"
              stroke="currentColor"
              strokeWidth="1.8"
              strokeLinejoin="round"
            />
            <path
              d="M9 12l2 2 4-4"
              stroke="currentColor"
              strokeWidth="1.8"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>

          <p>
            Мы не просим имя, почту, телефон или данные школы.
            Не указывайте их в тексте, если это не нужно для
            описания ситуации.
          </p>
        </div>
      </form>
    </PublicShell>
  )
}