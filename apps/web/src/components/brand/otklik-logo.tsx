import { cn } from "@/lib/utils"

export function OtklikLogo({
  compact = false,
  size = 36,
  className,
}: {
  compact?: boolean
  size?: number
  className?: string
}) {
  return (
    <span className={cn("inline-flex items-center gap-3 text-slate-950", className)}>
      <svg
        aria-hidden="true"
        width={size}
        height={size}
        viewBox="0 0 40 40"
        fill="none"
        className="shrink-0"
      >
        <rect width="40" height="40" rx="12" fill="#4F46E5" />
        <path
          d="M8.5 10.5h15a5 5 0 0 1 5 5v5a5 5 0 0 1-5 5h-7.2l-5.1 4.1.7-4.1H8.5a4 4 0 0 1-4-4v-7a4 4 0 0 1 4-4Z"
          fill="white"
        />
        <path
          d="M20.5 17h10a5 5 0 0 1 5 5v3.5a4 4 0 0 1-4 4h-2.2l.5 3-3.8-3h-5.5a5 5 0 0 1-5-5V22a5 5 0 0 1 5-5Z"
          fill="#C7D2FE"
          stroke="#4F46E5"
          strokeWidth="1.5"
        />
        <circle cx="21" cy="23.25" r="1.25" fill="#4F46E5" />
        <circle cx="25.5" cy="23.25" r="1.25" fill="#4F46E5" />
        <circle cx="30" cy="23.25" r="1.25" fill="#4F46E5" />
      </svg>
      {!compact ? (
        <span className="text-xl font-semibold tracking-[-0.025em]">Отклик</span>
      ) : null}
    </span>
  )
}
