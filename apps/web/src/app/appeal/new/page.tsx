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
        if (result.applicant_types.length) setApplicantType(result.applicant_types[0].code)
      })
      .catch(() => setError("Не удалось загрузить форму. Попробуйте обновить страницу."))
    return () => controller.abort()
  }, [])

  const formal =
    reference?.applicant_types.find((item) => item.code === applicantType)?.tone !==
    "informal"
  const selectedCategory = useMemo(
    () => reference?.categories.find((category) => category.id === categoryId),
    [categoryId, reference]
  )
  const descriptionRequired = pathChoice === "words" || selectedCategory?.requires_description

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
          Array.isArray(value) ? value.length > 0 : typeof value === "string" ? value.trim() : true
        )
      )
      const result = await publicAppealsApi.create({
        applicant_type: applicantType,
        category_id: categoryId || null,
        description: description.trim() || null,
        intake_answers: Object.keys(nonemptyAnswers).length ? nonemptyAnswers : null,
      })
      setCreated(result)
      await uploadFiles(files)
    } catch {
      setError("Не удалось отправить обращение. Проверьте форму и попробуйте ещё раз.")
    } finally {
      setBusy(false)
    }
  }

  async function copyTrack() {
    if (created) await navigator.clipboard.writeText(created.track_number)
  }

  function saveTrack() {
    if (!created) return
    const blob = new Blob(
      [`Номер обращения в Отклик: ${created.track_number}\n\nНе передавайте его посторонним.`],
      { type: "text/plain;charset=utf-8" }
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
      setError("Не удалось сохранить контакт. Обращение уже принято — попробуйте ещё раз позже.")
    }
  }

  if (created) {
    return (
      <PublicShell>
        <section className="mx-auto max-w-2xl space-y-6 py-8 sm:py-12">
          <div className="surface-card p-6 sm:p-9">
            <p className="font-medium text-teal-700">Обращение принято</p>
            <h1 className="mt-2 text-3xl font-semibold">Сохраните этот номер</h1>
            <p className="mt-3 text-sm leading-6 text-slate-600">
              Сервис не сможет восстановить номер. Он не сохранён в браузере и не
              находится в адресе страницы.
            </p>
            <div className="my-6 rounded-2xl bg-slate-950 p-5 text-center font-mono text-2xl tracking-[0.12em] text-white shadow-inner sm:text-4xl">
              {created.track_number}
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              <Button type="button" size="lg" onClick={copyTrack}>
                Копировать
              </Button>
              <Button type="button" size="lg" variant="outline" onClick={saveTrack}>
                Сохранить файлом
              </Button>
            </div>
          </div>

          {failedFiles.length ? (
            <div className="rounded-2xl border border-rose-200 bg-rose-50 p-5 text-sm text-rose-950">
              <p className="font-semibold">Обращение принято, но не все файлы загрузились.</p>
              <p className="mt-1">{failedFiles.map((file) => file.name).join(", ")}</p>
              <Button
                className="mt-3"
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

          {created.show_crisis_support ? (
            <>
              <CrisisPanel resources={created.crisis_support_resources} />
              <div className="surface-card space-y-3 p-5">
                <h2 className="font-semibold">Оставить контакт для экстренной связи — необязательно</h2>
                <p className="text-sm leading-6 text-slate-600">
                  Контакт будет зашифрован и сохранён отдельно. Это уменьшает
                  анонимность. Можно ничего не указывать — обращение уже принято.
                </p>
                <Input
                  value={contact}
                  maxLength={1000}
                  onChange={(event) => setContact(event.target.value)}
                  placeholder="Контакт, только если вы этого хотите"
                />
                <Button type="button" variant="outline" onClick={saveContact}>
                  Сохранить контакт
                </Button>
                {contactSaved ? <p className="text-sm text-teal-700">Контакт сохранён.</p> : null}
              </div>
            </>
          ) : null}

          {error ? <p className="text-sm text-rose-700">{error}</p> : null}
          <Link
            href="/appeal/current"
            className="block rounded-xl bg-teal-700 px-5 py-3 text-center font-medium text-white"
          >
            Посмотреть статус
          </Link>
        </section>
      </PublicShell>
    )
  }

  return (
    <PublicShell>
      <form onSubmit={submit} className="mx-auto max-w-3xl space-y-7 py-8 sm:py-12">
        <div className="space-y-3">
          <div className="flex items-center gap-3"><span className="rounded-full bg-teal-100 px-3 py-1 text-xs font-semibold text-teal-800">Шаг 1 из 1</span><span className="text-xs text-slate-500">Обычно 3–5 минут</span></div>
          <p className="text-sm font-semibold text-teal-700">Новое обращение</p>
          <h1 className="mt-2 text-3xl font-semibold tracking-tight">Расскажите, что произошло</h1>
          <p className="mt-2 text-slate-600">Все вопросы ниже, кроме выбора типа и темы/описания, необязательны.</p>
        </div>

        <fieldset className="surface-card space-y-3 p-5 sm:p-6">
          <legend className="px-1 font-semibold">Кто обращается?</legend>
          <div className="grid gap-2 sm:grid-cols-3">
            {reference?.applicant_types.map((item) => (
              <button
                key={item.code}
                type="button"
                className={`rounded-xl px-3 py-3 text-sm font-medium ring-1 ${
                  applicantType === item.code
                    ? "bg-teal-700 text-white ring-teal-700"
                    : "bg-white ring-slate-300"
                }`}
                onClick={() => setApplicantType(item.code)}
              >
                {item.label}
              </button>
            ))}
          </div>
        </fieldset>

        <section className="surface-card space-y-4 p-5 sm:p-6">
          <h2 className="font-semibold">Как удобнее рассказать?</h2>
          <div className="grid gap-3 sm:grid-cols-2">
            {([
              ["category", "Выбрать ситуацию", "Подойдёт, если тему легко определить"],
              ["words", "Рассказать своими словами", "Можно начать сразу со свободного текста"],
            ] as const).map(([value, title, text]) => (
              <button
                key={value}
                type="button"
                className={`rounded-2xl p-4 text-left ring-2 ${
                  pathChoice === value ? "bg-teal-50 ring-teal-600" : "ring-slate-200"
                }`}
                onClick={() => setPathChoice(value)}
              >
                <span className="font-semibold">{title}</span>
                <span className="mt-1 block text-sm text-slate-600">{text}</span>
              </button>
            ))}
          </div>

          {pathChoice === "category" ? (
            <div className="grid gap-2 sm:grid-cols-2">
              {reference?.categories.map((category) => (
                <button
                  key={category.id}
                  type="button"
                  className={`rounded-xl p-3 text-left text-sm ring-1 ${
                    categoryId === category.id
                      ? "bg-teal-700 text-white ring-teal-700"
                      : "ring-slate-300"
                  }`}
                  onClick={() => {
                    setCategoryId(category.id)
                    if (category.requires_description) setPathChoice("words")
                  }}
                >
                  {category.name}
                </button>
              ))}
            </div>
          ) : null}

          {(pathChoice === "words" || categoryId) && (
            <div className="space-y-2">
              <Label htmlFor="description">
                Опишите ситуацию {descriptionRequired ? "" : "(необязательно)"}
              </Label>
              <Textarea
                id="description"
                rows={7}
                maxLength={5000}
                required={Boolean(descriptionRequired)}
                value={description}
                onChange={(event) => setDescription(event.target.value)}
                placeholder={formal ? "Расскажите столько, сколько считаете нужным" : "Расскажи столько, сколько считаешь нужным"}
              />
            </div>
          )}
        </section>

        <section className="surface-card space-y-4 p-5 sm:p-6">
          <div>
            <h2 className="font-semibold">Несколько уточнений</h2>
            <p className="text-sm text-slate-600">Можно пропустить любой вопрос.</p>
          </div>
          {reference?.intake_questions
            .filter((question) => !categoryId || question.category_ids.includes(categoryId))
            .map((question) => {
              const required =
                question.required || question.required_category_ids.includes(categoryId)
              const value = answers[question.id]
              return (
                <div key={question.id} className="space-y-2">
                  <Label htmlFor={question.id}>
                    {question.label} {required ? "*" : ""}
                  </Label>
                  {question.help_text ? (
                    <p className="text-xs text-slate-500">{question.help_text}</p>
                  ) : null}
                  {question.field_type === "long_text" ? (
                    <Textarea
                      id={question.id}
                      required={required}
                      maxLength={question.max_length}
                      value={typeof value === "string" ? value : ""}
                      onChange={(event) =>
                        setAnswers((current) => ({
                          ...current,
                          [question.id]: event.target.value,
                        }))
                      }
                    />
                  ) : question.field_type === "single_choice" ? (
                    <select
                      id={question.id}
                      required={required}
                      className="h-10 w-full rounded-md border border-slate-300 bg-white px-3 text-sm"
                      value={typeof value === "string" ? value : ""}
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
                        const selected = Array.isArray(value) ? value : []
                        return (
                          <label key={option} className="flex items-center gap-2 text-sm">
                            <Checkbox
                              checked={selected.includes(option)}
                              onCheckedChange={(checked) =>
                                setAnswers((current) => ({
                                  ...current,
                                  [question.id]: checked
                                    ? [...selected, option]
                                    : selected.filter((item) => item !== option),
                                }))
                              }
                            />
                            {option}
                          </label>
                        )
                      })}
                    </div>
                  ) : question.field_type === "boolean" ? (
                    <label className="flex items-center gap-2 text-sm">
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
                      value={typeof value === "string" ? value : ""}
                      onChange={(event) =>
                        setAnswers((current) => ({
                          ...current,
                          [question.id]: event.target.value,
                        }))
                      }
                    />
                  )}
                </div>
              )
            })}
        </section>

        <section className="surface-card space-y-3 p-5 sm:p-6">
          <Label htmlFor="attachments">Скриншоты или изображения (необязательно)</Label>
          <Input
            id="attachments"
            type="file"
            accept="image/jpeg,image/png,image/webp"
            multiple
            onChange={(event) => selectFiles(event.target.files)}
          />
          <p className="text-xs text-slate-500">JPEG, PNG или WEBP; до 5 файлов и до 10 МБ каждый. Метаданные будут удалены.</p>
          {files.length ? <p className="text-sm">Выбрано файлов: {files.length}</p> : null}
        </section>

        {error ? <p className="rounded-xl bg-rose-50 p-4 text-sm text-rose-800">{error}</p> : null}
        <Button className="h-12 w-full text-base" type="submit" disabled={busy || !reference}>
          {busy ? "Отправляем…" : "Отправить обращение"}
        </Button>
        <p className="text-center text-xs leading-5 text-slate-500">
          Мы не просим имя, почту, телефон или данные школы. Не указывайте их в тексте,
          если это не нужно для описания ситуации.
        </p>
      </form>
    </PublicShell>
  )
}
