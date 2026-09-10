import Link from "next/link"

import { PublicShell } from "@/components/appeals/public-shell"

export default function Home() {
  return (
    <PublicShell>
      <section className="grid items-center gap-12 py-12 md:grid-cols-[1.15fr_.85fr] md:py-24">
        <div className="space-y-7">
          <p className="page-eyebrow">
            Анонимное доверенное обращение
          </p>
          <h1 className="max-w-2xl text-4xl leading-[1.1] font-semibold tracking-[-0.035em] text-slate-950 sm:text-5xl">
            О сложной ситуации можно рассказать без регистрации
          </h1>
          <p className="max-w-xl text-lg leading-8 text-slate-600">
            Обращение увидят специалисты. После отправки вы получите номер для
            безопасной проверки статуса — сохранить его сможете только вы.
          </p>
          <div className="flex flex-col gap-3 sm:flex-row">
            <Link
              href="/appeal/new"
              className="min-h-12 rounded-xl bg-indigo-600 px-6 py-3.5 text-center font-semibold text-white shadow-sm hover:bg-indigo-700 hover:shadow-md"
            >
              Отправить обращение
            </Link>
            <Link
              href="/appeal/check"
              className="min-h-12 rounded-xl bg-white px-6 py-3.5 text-center font-semibold shadow-sm ring-1 ring-slate-200 hover:bg-indigo-50 hover:text-indigo-800"
            >
              Проверить обращение
            </Link>
          </div>
        </div>
        <div className="grid gap-3 self-center">
          {[
            ["1", "Расскажите", "Выберите тему или опишите ситуацию своими словами."],
            ["2", "Сохраните номер", "Мы не храним его в открытом виде и не сможем восстановить."],
            ["3", "Проверяйте статус", "Введите номер позже — аккаунт не нужен."],
          ].map(([number, title, text]) => (
            <article key={number} className="surface-card p-6">
              <div className="flex gap-4">
                <span className="flex size-8 shrink-0 items-center justify-center rounded-full bg-indigo-100 font-semibold text-indigo-800">
                  {number}
                </span>
                <div>
                  <h2 className="text-lg font-semibold">{title}</h2>
                  <p className="mt-1 text-[15px] leading-6 text-slate-600">{text}</p>
                </div>
              </div>
            </article>
          ))}
        </div>
      </section>
      <section className="rounded-2xl border border-indigo-100 bg-indigo-50 p-6 text-slate-900 sm:p-9">
        <p className="text-xs font-semibold tracking-[0.16em] text-indigo-700 uppercase">Приватность</p>
        <h2 className="mt-2 text-xl font-semibold">Конфиденциальность по умолчанию</h2>
        <p className="mt-2 max-w-3xl leading-7 text-slate-600">
          Отклик не создаёт аккаунт заявителя и не просит имя, почту, телефон или
          школу. Текст и ответы хранятся в зашифрованном виде отдельно от служебных
          данных.
        </p>
      </section>
    </PublicShell>
  );
}
