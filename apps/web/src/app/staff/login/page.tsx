"use client"

import { useEffect, useState, type FormEvent } from "react"
import { useRouter } from "next/navigation"

import { OtklikLogo } from "@/components/brand/otklik-logo"
import { Button } from "@/components/ui/button"
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
      router.replace(
        staff.must_change_password
          ? "/staff/change-password"
          : staffHome(staff.role),
      )
    }
  }, [router, staff, status])

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setSubmitting(true)
    setError(null)

    try {
      const profile = await login(loginValue, password)
      setPassword("")
      router.replace(
        profile.must_change_password
          ? "/staff/change-password"
          : staffHome(profile.role),
      )
    } catch {
      setError("Не удалось войти. Проверьте логин и пароль.")
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <main className="relative min-h-screen overflow-hidden bg-[#f8f8fb] text-[#15131d]">
      {/* Background glow */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 overflow-hidden"
      >
        <div className="absolute -left-40 -top-40 h-[520px] w-[520px] rounded-full bg-violet-300/20 blur-[110px]" />
        <div className="absolute -right-32 top-1/4 h-[480px] w-[480px] rounded-full bg-cyan-300/15 blur-[110px]" />
        <div className="absolute bottom-[-220px] left-1/3 h-[520px] w-[520px] rounded-full bg-purple-300/10 blur-[120px]" />

        <div
          className="absolute inset-0 opacity-[0.35]"
          style={{
            backgroundImage:
              "linear-gradient(rgba(105,88,180,.035) 1px, transparent 1px), linear-gradient(90deg, rgba(105,88,180,.035) 1px, transparent 1px)",
            backgroundSize: "42px 42px",
          }}
        />
      </div>

      {/* Content */}
      <div className="relative z-10 flex min-h-screen items-center justify-center px-4 py-8 sm:px-6">
        <div className="w-full max-w-[460px]">
          {/* Logo / brand */}
          <div className="mb-7 flex justify-center">
            <div className="rounded-[22px] border border-white/80 bg-white/75 p-3 shadow-[0_18px_50px_rgba(81,65,145,.10)] backdrop-blur-xl">
              <OtklikLogo size={46} />
            </div>
          </div>

          {/* Login card */}
          <div className="overflow-hidden rounded-[30px] border border-white/80 bg-white/80 shadow-[0_30px_90px_rgba(57,45,105,.14)] backdrop-blur-2xl">
            {/* Card top accent */}
            <div className="h-1.5 bg-gradient-to-r from-[#6d5df6] via-[#7564f8] to-[#55cde7]" />

            <div className="p-6 sm:p-9">
              {/* Header */}
              <div className="mb-8 text-center">
                <div className="mb-3 inline-flex rounded-full border border-[#e9e5ff] bg-[#f4f1ff] px-3 py-1 text-xs font-semibold tracking-wide text-[#6754e8]">
                  РАБОЧЕЕ ПРОСТРАНСТВО
                </div>

                <h1 className="text-[28px] font-bold tracking-[-0.03em] text-[#14121b] sm:text-[32px]">
                  Вход для сотрудников
                </h1>

                <p className="mx-auto mt-2 max-w-[330px] text-sm leading-6 text-[#777580]">
                  Защищённое рабочее пространство Отклика.
                </p>
              </div>

              {/* Form */}
              <form className="space-y-5" onSubmit={handleSubmit}>
                <div className="space-y-2">
                  <Label
                    htmlFor="login"
                    className="text-[13px] font-semibold text-[#34313f]"
                  >
                    Логин
                  </Label>

                  <Input
                    id="login"
                    name="login"
                    autoComplete="username"
                    required
                    value={loginValue}
                    onChange={(event) => setLoginValue(event.target.value)}
                    placeholder="Введите логин"
                    className="h-12 rounded-[15px] border-[#e5e2ec] bg-white/80 px-4 text-[15px] shadow-none transition-all placeholder:text-[#aaa7b1] focus:border-[#7564f8] focus:ring-4 focus:ring-[#7564f8]/10"
                  />
                </div>

                <div className="space-y-2">
                  <Label
                    htmlFor="password"
                    className="text-[13px] font-semibold text-[#34313f]"
                  >
                    Пароль
                  </Label>

                  <Input
                    id="password"
                    name="password"
                    type="password"
                    autoComplete="current-password"
                    required
                    value={password}
                    onChange={(event) => setPassword(event.target.value)}
                    placeholder="Введите пароль"
                    className="h-12 rounded-[15px] border-[#e5e2ec] bg-white/80 px-4 text-[15px] shadow-none transition-all placeholder:text-[#aaa7b1] focus:border-[#7564f8] focus:ring-4 focus:ring-[#7564f8]/10"
                  />
                </div>

                {error ? (
                  <div
                    role="alert"
                    className="rounded-[15px] border border-red-200/80 bg-red-50/80 px-4 py-3 text-sm leading-5 text-red-600"
                  >
                    {error}
                  </div>
                ) : null}

                <Button
                  className="h-12 w-full rounded-[15px] border-0 bg-gradient-to-r from-[#6b5af5] to-[#7664f8] text-[15px] font-semibold text-white shadow-[0_12px_28px_rgba(105,86,238,.25)] transition-all duration-200 hover:-translate-y-0.5 hover:from-[#604eeb] hover:to-[#6d5af0] hover:shadow-[0_16px_34px_rgba(105,86,238,.30)] disabled:translate-y-0 disabled:opacity-60"
                  type="submit"
                  disabled={submitting}
                >
                  {submitting ? "Входим…" : "Войти"}
                </Button>
              </form>

              {/* Footer */}
              <div className="mt-7 flex items-center justify-center gap-2 text-xs text-[#9996a0]">
                <span className="h-1.5 w-1.5 rounded-full bg-[#6d5df6]" />
                <span>Отклик · защищённая зона</span>
              </div>
            </div>
          </div>

          {/* Bottom hint */}
          <p className="mt-6 text-center text-xs leading-5 text-[#aaa7b1]">
            Доступ предназначен только для авторизованных сотрудников
          </p>
        </div>
      </div>
    </main>
  )
}