"use client"

import { useQuery } from "@tanstack/react-query"

import { ApiError, apiClient } from "@/lib/api"
import { runtimeConfig } from "@/lib/config"

type ReadinessResponse = {
  status: "ok" | "unavailable"
  services: {
    application: "ok" | "unavailable"
    database: "ok" | "unavailable"
    valkey: "ok" | "unavailable"
  }
}

export function DevelopmentDiagnostics() {
  const readiness = useQuery({
    queryKey: ["development", "backend-readiness"],
    queryFn: ({ signal }) =>
      apiClient.get<ReadinessResponse>("/api/v1/health/ready", { signal }),
  })

  let label = "Checking backend readiness…"
  let indicatorClass = "bg-amber-500"

  if (readiness.isSuccess) {
    label = "Backend and infrastructure are ready"
    indicatorClass = "bg-emerald-500"
  } else if (readiness.isError) {
    label =
      readiness.error instanceof ApiError
        ? `Backend responded but is not ready (HTTP ${readiness.error.status})`
        : "Backend readiness endpoint is unreachable"
    indicatorClass = "bg-red-500"
  }

  return (
    <section
      aria-labelledby="diagnostics-title"
      className="w-full rounded-xl border border-black/10 bg-zinc-50 p-4 dark:border-white/15 dark:bg-zinc-900"
    >
      <h2 id="diagnostics-title" className="text-sm font-semibold">
        Development diagnostics
      </h2>
      <div className="mt-2 flex items-center gap-2 text-sm text-zinc-600 dark:text-zinc-400">
        <span
          aria-hidden="true"
          className={`size-2 shrink-0 rounded-full ${indicatorClass}`}
        />
        <span aria-live="polite">{label}</span>
      </div>
      <p className="mt-2 truncate font-mono text-xs text-zinc-500">
        {runtimeConfig.apiBaseUrl}/api/v1/health/ready
      </p>
    </section>
  )
}

