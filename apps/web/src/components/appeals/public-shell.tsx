import Link from "next/link"
import type { ReactNode } from "react"

import { OtklikLogo } from "@/components/brand/otklik-logo"

export function PublicShell({ children }: { children: ReactNode }) {
  return (
    <div className="otklik-shell">
      {/* Декоративный фон */}
      <div className="shell-orb shell-orb-one" />
      <div className="shell-orb shell-orb-two" />
      <div className="shell-orb shell-orb-three" />

      {/* Очень тонкая сетка */}
      <div className="shell-grid" />

      {/* HEADER */}
      <header className="otklik-header">
        <div className="otklik-header-inner">

          {/* LOGO */}
          <Link
            href="/"
            aria-label="Отклик — на главную"
            className="otklik-brand group"
          >
            <div className="otklik-logo-wrap">
              <OtklikLogo size={38} />
            </div>
          </Link>

          {/* NAVIGATION */}
          <nav
            aria-label="Основная навигация"
            className="otklik-nav"
          >
            <Link
              href="/appeal/new"
              className="otklik-nav-link"
            >
              <span>Обратиться</span>
              <svg
                width="15"
                height="15"
                viewBox="0 0 24 24"
                fill="none"
                aria-hidden="true"
              >
                <path
                  d="M5 12h14M13 6l6 6-6 6"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
            </Link>

            <Link
              href="/appeal/check"
              className="otklik-check-button"
            >
              <span className="otklik-check-icon">
                <svg
                  width="15"
                  height="15"
                  viewBox="0 0 24 24"
                  fill="none"
                  aria-hidden="true"
                >
                  <path
                    d="M9 12l2 2 4-4"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                  <path
                    d="M12 3l7 4v5c0 4.5-3 7.5-7 9-4-1.5-7-4.5-7-9V7l7-4z"
                    stroke="currentColor"
                    strokeWidth="1.7"
                    strokeLinejoin="round"
                  />
                </svg>
              </span>

              <span>Проверить обращение</span>
            </Link>

            {/* STATUS */}
            <div className="otklik-status">
              <span className="otklik-status-dot">
                <span />
              </span>

              <span>Без регистрации</span>
            </div>
          </nav>
        </div>

        {/* Нижняя светящаяся линия */}
        <div className="header-light-line" />
      </header>

      {/* MAIN */}
      <main className="otklik-main">
        {children}
      </main>

      {/* FOOTER */}
      <footer className="otklik-footer">
        <div className="otklik-footer-inner">
          <div className="footer-brand">
            <div className="footer-logo">
              <OtklikLogo size={30} />
            </div>

            <div>
              <strong>Отклик</strong>
              <span>Анонимное доверенное обращение</span>
            </div>
          </div>

          <div className="footer-security">
            <span className="footer-security-icon">
              <svg
                width="15"
                height="15"
                viewBox="0 0 24 24"
                fill="none"
                aria-hidden="true"
              >
                <path
                  d="M12 3l7 4v5c0 4.5-3 7.5-7 9-4-1.5-7-4.5-7-9V7l7-4z"
                  stroke="currentColor"
                  strokeWidth="1.8"
                  strokeLinejoin="round"
                />
                <path
                  d="M9 12l2 2 4-4"
                  stroke="currentColor"
                  strokeWidth="1.8"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
            </span>

            <span>Не сообщайте номер обращения посторонним</span>
          </div>
        </div>
      </footer>
    </div>
  )
}