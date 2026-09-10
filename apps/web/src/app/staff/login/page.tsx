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
import { staffHome, useAuth } from "@/lib/auth"

export default function StaffLoginPage() {
  const router = useRouter()
  const { staff, status, login } = useAuth()
  const [loginValue, setLoginValue] = useState("")
  const [password, setPassword] = useState("")
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    if (status === "authenticated" && staff) {
      router.replace(staff.must_change_password ? "/staff/change-password" : staffHome(staff.role))
    }
  }, [router, staff, status])

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setSubmitting(true)
    setError(null)
    try {
      const profile = await login(loginValue, password)
      setPassword("")
      router.replace(profile.must_change_password ? "/staff/change-password" : staffHome(profile.role))
    } catch {
      setError("Не удалось войти. Проверьте логин и пароль.")
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <main className="grid min-h-screen place-items-center bg-[radial-gradient(circle_at_top,#d9f5ec,transparent_35%),linear-gradient(#f9fffc,#f2f5f6)] p-4">
      <Card className="w-full max-w-md border-slate-200/80 shadow-[0_30px_80px_-45px_rgba(15,23,42,.5)]">
        <CardHeader>
          <div className="mb-3 flex size-11 items-center justify-center rounded-2xl bg-teal-700 font-semibold text-white">О</div>
          <CardTitle className="text-2xl">Вход для сотрудников</CardTitle>
          <CardDescription>Защищённое рабочее пространство Отклика.</CardDescription>
        </CardHeader>
        <CardContent>
          <form className="space-y-4" onSubmit={handleSubmit}>
            <div className="space-y-2">
              <Label htmlFor="login">Логин</Label>
              <Input
                id="login"
                name="login"
                autoComplete="username"
                required
                value={loginValue}
                onChange={(event) => setLoginValue(event.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="password">Пароль</Label>
              <Input
                id="password"
                name="password"
                type="password"
                autoComplete="current-password"
                required
                value={password}
                onChange={(event) => setPassword(event.target.value)}
              />
            </div>
            {error ? (
              <p role="alert" className="text-sm text-destructive">
                {error}
              </p>
            ) : null}
            <Button className="w-full" type="submit" disabled={submitting}>
              {submitting ? "Входим…" : "Войти"}
            </Button>
          </form>
        </CardContent>
      </Card>
    </main>
  )
}
