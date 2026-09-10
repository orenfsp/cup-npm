import Link from "next/link"

import { PublicShell } from "@/components/appeals/public-shell"

export default function Home() {
  return (
    <PublicShell>
      <div className="home">

        {/* HERO */}
        <section className="home-hero">

          {/* Мягкое свечение */}
          <div className="hero-glow hero-glow-left" />
          <div className="hero-glow hero-glow-right" />

          <div className="hero-content">

            <div className="hero-label">
              <span className="hero-label-dot">
                <span />
              </span>

              <span>Анонимная психологическая помощь</span>
            </div>

            <h1 className="hero-title">
              Не обязательно
              <br />
              справляться
              <br />
              <span>со всем одному.</span>
            </h1>

            <p className="hero-description">
              Расскажите, что происходит.
              <br className="hidden sm:block" />
              {" "}Вас услышат и помогут разобраться в ситуации.
            </p>

            <div className="hero-actions">

              <Link
                href="/appeal/new"
                className="hero-primary"
              >
                <span>Рассказать о ситуации</span>

                <span className="hero-primary-arrow">
                  <svg
                    width="18"
                    height="18"
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
                </span>
              </Link>

              <Link
                href="/appeal/check"
                className="hero-secondary"
              >
                Проверить обращение
              </Link>

            </div>

            <div className="hero-trust">

              <div className="trust-item">
                <span className="trust-icon">
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
                  </svg>
                </span>

                <span>Анонимно</span>
              </div>

              <span className="trust-divider" />

              <div className="trust-item">
                <span className="trust-icon">
                  <svg
                    width="15"
                    height="15"
                    viewBox="0 0 24 24"
                    fill="none"
                    aria-hidden="true"
                  >
                    <path
                      d="M4 5.5A2.5 2.5 0 016.5 3h11A2.5 2.5 0 0120 5.5v8a2.5 2.5 0 01-2.5 2.5H13l-4 4v-4H6.5A2.5 2.5 0 014 13.5v-8z"
                      stroke="currentColor"
                      strokeWidth="1.8"
                      strokeLinejoin="round"
                    />
                  </svg>
                </span>

                <span>Без регистрации</span>
              </div>

              <span className="trust-divider" />

              <div className="trust-item">
                <span className="trust-icon">
                  <svg
                    width="15"
                    height="15"
                    viewBox="0 0 24 24"
                    fill="none"
                    aria-hidden="true"
                  >
                    <path
                      d="M12 21s8-4.5 8-11V5l-8-3-8 3v5c0 6.5 8 11 8 11z"
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

                <span>Конфиденциально</span>
              </div>

            </div>
          </div>

          {/* HERO VISUAL */}
          <div className="hero-visual">

            <div className="visual-aura" />

            <div className="visual-orbit orbit-one" />
            <div className="visual-orbit orbit-two" />

            <div className="message-card">

              <div className="message-card-top">
                <div className="message-status">
                  <span />
                  Защищённый канал
                </div>

                <span className="message-number">
                  № ····
                </span>
              </div>

              <div className="message-line" />

              <div className="message-icon">
                <div className="message-icon-ring">
                  <svg
                    width="27"
                    height="27"
                    viewBox="0 0 24 24"
                    fill="none"
                    aria-hidden="true"
                  >
                    <path
                      d="M5 12l4 4L19 6"
                      stroke="currentColor"
                      strokeWidth="2"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    />
                  </svg>
                </div>
              </div>

              <div className="message-card-title">
                Ваш голос услышан
              </div>

              <div className="message-card-text">
                Обращение передано
                <br />
                специалистам
              </div>

              <div className="message-card-bottom">
                <span className="message-live-dot" />
                <span>Можно проверить статус позже</span>
              </div>

            </div>

            {/* Плавающая подсказка */}
            <div className="floating-note floating-note-one">
              <span className="floating-note-icon">
                <svg
                  width="14"
                  height="14"
                  viewBox="0 0 24 24"
                  fill="none"
                  aria-hidden="true"
                >
                  <path
                    d="M12 3v18M3 12h18"
                    stroke="currentColor"
                    strokeWidth="1.7"
                    strokeLinecap="round"
                  />
                </svg>
              </span>

              <span>Можно начать с одного сообщения</span>
            </div>

            <div className="floating-note floating-note-two">
              <span className="floating-check">
                ✓
              </span>

              <span>Без имени и регистрации</span>
            </div>

          </div>

        </section>


        {/* BOTTOM MESSAGE */}
        <section className="home-bottom">

          <div className="bottom-line" />

          <div className="bottom-content">

            <div className="bottom-number">
              01
            </div>

            <div className="bottom-text">
              <strong>
                Не знаете, с чего начать?
              </strong>

              <span>
                Это нормально. Просто опишите ситуацию своими словами —
                не нужно подбирать правильные слова.
              </span>
            </div>

            <Link
              href="/appeal/new"
              className="bottom-link"
            >
              Начать разговор

              <svg
                width="17"
                height="17"
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

          </div>

        </section>

      </div>
    </PublicShell>
  )
}