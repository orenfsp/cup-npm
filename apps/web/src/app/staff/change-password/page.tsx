"use client"

import { useEffect, useState, type FormEvent } from "react"
import { useRouter } from "next/navigation"

import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { ApiError } from "@/lib/api"
import { staffHome, useAuth } from "@/lib/auth"

export default function ChangePasswordPage() {
  const router = useRouter()
  const { staff, status, request, logout } = useAuth()
  const [password, setPassword] = useState("")
  const [confirmation, setConfirmation] = useState("")
  const [error, setError] = useState("")
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    if (status === "anonymous") router.replace("/staff/login")
    else if (status === "authenticated" && staff && !staff.must_change_password) {
      router.replace(staffHome(staff.role))
    }
  }, [router, staff, status])

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError("")
    if (password !== confirmation) {
      setError("Пароли не совпадают.")
      return
    }
    setBusy(true)
    try {
      await request("api/v1/auth/change-password", {
        method: "POST",
        json: { password },
      })
      setPassword("")
      setConfirmation("")
      await logout()
      router.replace("/staff/login")
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Не удалось изменить пароль.")
    } finally {
      setBusy(false)
    }
  }

  return (
    <main className="grid min-h-screen place-items-center bg-[radial-gradient(circle_at_top,#d9f5ec,transparent_35%),linear-gradient(#f9fffc,#f2f5f6)] p-4">
      <Card className="w-full max-w-md border-slate-200/80 shadow-[0_30px_80px_-45px_rgba(15,23,42,.5)]">
        <CardHeader>
          <div className="mb-3 flex size-11 items-center justify-center rounded-2xl bg-teal-700 font-semibold text-white">О</div>
          <CardTitle>Измените временный пароль</CardTitle>
          <CardDescription>
            Перед началом работы задайте постоянный пароль длиной не менее 12 символов.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form className="space-y-4" onSubmit={submit}>
            <div className="space-y-2">
              <Label htmlFor="new-password">Новый пароль</Label>
              <Input id="new-password" type="password" autoComplete="new-password" minLength={12} required value={password} onChange={(event) => setPassword(event.target.value)} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="confirm-password">Повторите пароль</Label>
              <Input id="confirm-password" type="password" autoComplete="new-password" minLength={12} required value={confirmation} onChange={(event) => setConfirmation(event.target.value)} />
            </div>
            {error ? <p role="alert" className="text-sm text-destructive">{error}</p> : null}
            <Button type="submit" className="w-full" disabled={busy}>{busy ? "Сохраняем…" : "Сохранить"}</Button>
          </form>
        </CardContent>
      </Card>
    </main>
  )
}
