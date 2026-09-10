import Link from "next/link"

import { PublicShell } from "@/components/appeals/public-shell"

export default function Home() {
  return (
    <PublicShell>
      <section className="grid items-center gap-10 py-10 md:grid-cols-[1.15fr_.85fr] md:py-20">
        <div className="space-y-6">
          <p className="text-sm font-semibold tracking-[0.18em] text-teal-700 uppercase">
            Анонимное доверенное обращение
          </p>
          <h1 className="max-w-2xl text-4xl leading-[1.08] font-semibold tracking-[-0.035em] text-slate-950 sm:text-6xl">
            О сложной ситуации можно рассказать без регистрации
          </h1>
          <p className="max-w-xl text-lg leading-8 text-slate-600">
            Обращение увидят специалисты. После отправки вы получите номер для
            безопасной проверки статуса — сохранить его сможете только вы.
          </p>
          <div className="flex flex-col gap-3 sm:flex-row">
            <Link
              href="/appeal/new"
              className="rounded-xl bg-teal-700 px-6 py-3.5 text-center font-medium text-white shadow-lg shadow-teal-900/10 hover:-translate-y-0.5 hover:bg-teal-800"
            >
              Отправить обращение
            </Link>
            <Link
              href="/appeal/check"
              className="rounded-xl bg-white px-6 py-3.5 text-center font-medium shadow-sm ring-1 ring-slate-200 hover:-translate-y-0.5 hover:bg-slate-50"
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
            <article key={number} className="surface-card p-5">
              <div className="flex gap-4">
                <span className="flex size-8 shrink-0 items-center justify-center rounded-full bg-teal-100 font-semibold text-teal-800">
                  {number}
                </span>
                <div>
                  <h2 className="font-semibold">{title}</h2>
                  <p className="mt-1 text-sm leading-6 text-slate-600">{text}</p>
                </div>
              </div>
            </article>
          ))}
        </div>
      </section>
      <section className="relative overflow-hidden rounded-3xl bg-teal-950 p-6 text-teal-50 shadow-xl shadow-teal-950/10 sm:p-9">
        <div className="absolute -top-16 -right-10 size-48 rounded-full bg-teal-700/30 blur-3xl" />
        <p className="relative text-xs font-semibold tracking-[0.16em] text-teal-300 uppercase">Приватность</p>
        <h2 className="relative mt-2 text-xl font-semibold">Конфиденциальность по умолчанию</h2>
        <p className="mt-2 max-w-3xl leading-7 text-teal-100">
          Отклик не создаёт аккаунт заявителя и не просит имя, почту, телефон или
          школу. Текст и ответы хранятся в зашифрованном виде отдельно от служебных
          данных.
        </p>
      </section>
    </PublicShell>
  );
}
