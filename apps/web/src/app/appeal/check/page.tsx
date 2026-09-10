"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"

import { PublicShell } from "@/components/appeals/public-shell"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { publicAppealsApi } from "@/lib/appeals"

export default function CheckAppealPage() {
  const router = useRouter()
  const [trackNumber, setTrackNumber] = useState("")
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState("")

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setBusy(true)
    setError("")
    try {
      await publicAppealsApi.access(trackNumber)
      setTrackNumber("")
      router.replace("/appeal/current")
    } catch {
      setError("Номер неверен или обращение сейчас недоступно. Проверьте ввод и попробуйте снова.")
    } finally {
      setBusy(false)
    }
  }

  return (
    <PublicShell>
      <form
        onSubmit={submit}
        className="surface-card mx-auto mt-10 max-w-xl space-y-7 p-6 sm:mt-20 sm:p-10"
      >
        <div>
          <p className="page-eyebrow">Безопасный доступ</p>
          <h1 className="mt-2 text-3xl font-semibold sm:text-[32px]">Введите сохранённый номер</h1>
          <p className="mt-2 text-base leading-7 text-slate-600">
            Номер используется только для этой проверки и не появится в адресе страницы.
          </p>
        </div>
        <div className="space-y-2">
          <Label htmlFor="track-number">Номер обращения</Label>
          <Input
            id="track-number"
            value={trackNumber}
            onChange={(event) => setTrackNumber(event.target.value.toUpperCase())}
            placeholder="ОТК-XXXX-XXXX"
            autoComplete="off"
            spellCheck={false}
            maxLength={40}
            required
            className="h-14 text-center font-mono text-lg tracking-[0.12em]"
          />
        </div>
        {error ? <p className="state-error" role="alert">{error}</p> : null}
        <Button className="h-11 w-full" type="submit" disabled={busy}>
          {busy ? "Проверяем…" : "Открыть статус"}
        </Button>
      </form>
    </PublicShell>
  )
}
