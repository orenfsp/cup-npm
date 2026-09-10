"use client"

import { useEffect, useState, type FormEvent } from "react"
import { useRouter } from "next/navigation"

import { OtklikLogo } from "@/components/brand/otklik-logo"
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
    <main className="grid min-h-screen place-items-center bg-[#f5f6fa] p-4">
      <Card className="w-full max-w-md border-slate-200 shadow-[0_20px_50px_-35px_rgba(30,41,59,.35)]">
        <CardHeader>
          <OtklikLogo className="mb-4" size={42} />
          <CardTitle className="text-xl">Измените временный пароль</CardTitle>
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
            {error ? <p role="alert" className="state-error">{error}</p> : null}
            <Button type="submit" className="w-full" disabled={busy}>{busy ? "Сохраняем…" : "Сохранить"}</Button>
          </form>
        </CardContent>
      </Card>
    </main>
  )
}
