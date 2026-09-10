import { cn } from "@/lib/utils"

const labels: Record<string, string> = {
  new: "Новое",
  assigned: "Назначено",
  in_progress: "В работе",
  needs_clarification: "Нужно уточнение",
  answer_ready: "Ответ готов",
  returned: "Возвращено",
  completed: "Завершено",
  rejected: "Отклонено",
  closed_no_response: "Закрыто без ответа",
  low: "Низкий",
  standard: "Обычный",
  urgent: "Срочный",
  crisis: "Кризисный флаг",
  overdue: "Просрочено",
}

const tones: Record<string, string> = {
  new: "border-blue-200 bg-blue-50 text-blue-800",
  assigned: "border-indigo-200 bg-indigo-50 text-indigo-800",
  in_progress: "border-violet-200 bg-violet-50 text-violet-800",
  needs_clarification: "border-amber-200 bg-amber-50 text-amber-900",
  answer_ready: "border-cyan-200 bg-cyan-50 text-cyan-900",
  returned: "border-orange-200 bg-orange-50 text-orange-900",
  completed: "border-emerald-200 bg-emerald-50 text-emerald-800",
  rejected: "border-rose-200 bg-rose-50 text-rose-800",
  closed_no_response: "border-slate-200 bg-slate-100 text-slate-700",
  low: "border-slate-200 bg-slate-50 text-slate-700",
  standard: "border-slate-200 bg-slate-50 text-slate-700",
  urgent: "border-rose-200 bg-rose-50 text-rose-800",
  crisis: "border-red-300 bg-red-50 text-red-800",
  overdue: "border-amber-300 bg-amber-50 text-amber-900",
}

export function StatusBadge({
  value,
  label,
  className,
}: {
  value: string
  label?: string
  className?: string
}) {
  return (
    <span
      className={cn(
        "inline-flex min-h-6 items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-semibold leading-none",
        tones[value] ?? tones.standard,
        className
      )}
    >
      <span className="size-1.5 rounded-full bg-current opacity-70" aria-hidden="true" />
      {label ?? labels[value] ?? value}
    </span>
  )
}
