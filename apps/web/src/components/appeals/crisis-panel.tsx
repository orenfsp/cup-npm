import type { CrisisResource } from "@/lib/appeals"

export function CrisisPanel({ resources }: { resources: CrisisResource[] }) {
  return (
    <aside aria-label="Ресурсы экстренной помощи" className="space-y-4 rounded-3xl border border-amber-200 bg-amber-50/90 p-5 text-amber-950 shadow-[0_18px_50px_-38px_rgba(146,64,14,.5)] sm:p-6">
      <div><p className="text-xs font-semibold tracking-wide text-amber-700 uppercase">Поддержка рядом</p><h2 className="mt-1 text-lg font-semibold">Если прямо сейчас небезопасно</h2></div>
      {resources.map((resource) => (
        <div key={`${resource.title}-${resource.message}`} className="space-y-2 rounded-2xl bg-white/70 p-4">
          <h3 className="font-semibold">{resource.title}</h3>
          <p className="text-sm leading-6">{resource.message}</p>
          <div className="flex flex-wrap gap-3 text-sm font-medium">
            {resource.phone ? <a href={`tel:${resource.phone}`}>{resource.phone}</a> : null}
            {resource.url ? (
              <a href={resource.url} rel="noreferrer" target="_blank">
                Открыть ресурс помощи
              </a>
            ) : null}
          </div>
        </div>
      ))}
      <p className="text-xs text-amber-800">
        Эта подсказка не мешает отправить или просматривать обращение.
      </p>
    </aside>
  )
}
