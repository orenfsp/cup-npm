"use client"

import { useState } from "react"
import Link from "next/link"

import { OtklikLogo } from "@/components/brand/otklik-logo"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { setupStaffPassword } from "@/lib/admin"

export function SetupPasswordForm({ token }: { token: string }) {
  const [password, setPassword] = useState("")
  const [confirmation, setConfirmation] = useState("")
  const [busy, setBusy] = useState(false)
  const [done, setDone] = useState(false)
  const [error, setError] = useState("")

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError("")
    if (!token) return setError("Ссылка настройки пароля неполная.")
    if (password.length < 12) return setError("Пароль должен содержать не менее 12 символов.")
    if (password !== confirmation) return setError("Пароли не совпадают.")
    setBusy(true)
    try {
      await setupStaffPassword(token, password)
      setDone(true)
      setPassword("")
      setConfirmation("")
    } catch {
      setError("Ссылка недействительна, истекла или уже использована.")
    } finally {
      setBusy(false)
    }
  }

  return (
    <main className="grid min-h-screen place-items-center bg-[#f5f6fa] p-4">
      <Card className="w-full max-w-md border-slate-200 shadow-[0_20px_50px_-35px_rgba(30,41,59,.35)]">
        <CardHeader><OtklikLogo className="mb-3" size={42} /><CardTitle className="text-xl">Настройка пароля</CardTitle></CardHeader>
        <CardContent>
          {done ? (
            <div className="space-y-4">
              <p className="state-success">Пароль установлен. Ссылка больше не действует.</p>
              <Button render={<Link href="/staff/login" />}>Перейти ко входу</Button>
            </div>
          ) : (
            <form className="space-y-4" onSubmit={submit}>
              <div className="space-y-2">
                <Label htmlFor="password">Новый пароль</Label>
                <Input id="password" type="password" minLength={12} required value={password} onChange={(event) => setPassword(event.target.value)} />
              </div>
              <div className="space-y-2">
                <Label htmlFor="confirmation">Повторите пароль</Label>
                <Input id="confirmation" type="password" minLength={12} required value={confirmation} onChange={(event) => setConfirmation(event.target.value)} />
              </div>
              {error ? <p className="state-error" role="alert">{error}</p> : null}
              <Button className="w-full" disabled={busy || !token}>{busy ? "Сохраняем…" : "Установить пароль"}</Button>
            </form>
          )}
        </CardContent>
      </Card>
    </main>
  )
}
