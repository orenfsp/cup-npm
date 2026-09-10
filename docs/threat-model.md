# Otklik MVP threat model

This document describes the Phase 5 security assumptions and limits. It is a living
model, not a claim that the current foundation is a complete production system.

## Assets

- Original appeal contents and encrypted intake answers
- Applicant/specialist chat messages
- Internal staff notes
- Optional crisis contact details
- Attachment contents and metadata
- Raw track access secrets and their lookup digests
- Staff credentials and authenticated sessions
- Security audit records and cryptographic keys

## Primary threats

- A database or backup leak exposing operational metadata or ciphertext
- A stolen track number allowing unauthorized access to an appeal
- Brute-force or enumeration attacks against track lookup
- A compromised staff account reading or changing appeals
- Excessive staff permissions, including experts seeing operator-only crisis contacts or
  complaints
- Application, proxy, or infrastructure logs leaking appeal content, credentials, tokens,
  authorization headers, contact data, or raw track numbers
- Attachment filenames, embedded metadata, storage paths, or public URLs leaking identity
- Accidental administrator access to sensitive text without a justified operational need
- Database snapshots, storage backups, or encryption-key backups being exposed together
- Key or nonce misuse weakening encrypted content protection

## Trust boundaries

Data crosses the following boundaries:

1. The applicant or staff browser, which handles plaintext before transport.
2. A future reverse proxy, which may terminate TLS and transiently observe network metadata.
3. FastAPI, which validates requests and will perform authorization and cryptography.
4. PostgreSQL, which stores operational metadata, HMAC digests, and encrypted sensitive
   fields.
5. Valkey, which will hold short-lived coordination and rate-limit state, not durable appeal
   content.
6. Private file storage, which stores encrypted attachment bytes under opaque keys.

Connections between these boundaries require transport security in deployment. Application
authorization must be enforced even when infrastructure is on a private network.

## Current controls

- There is no applicant identity or account record.
- Appeal metadata is separated from encrypted content, chat, notes, intake answers, and
  crisis contacts.
- Raw track codes are returned only at creation and never persisted; lookup uses the unique
  HMAC-SHA256 digest.
- Successful track verification creates a short-lived signed HttpOnly capability scoped to
  one appeal.
- Sensitive database fields use a versioned AES-256-GCM envelope foundation.
- Crisis contacts and internal notes have dedicated tables to support narrow future access
  policy.
- Images are magic-byte checked, decoded with pixel bounds, re-encoded without source metadata,
  AES-GCM encrypted, and placed in private storage without an original filename or public URL.
- Public track checks and submissions use expiring Valkey counters keyed only by an HMAC of the
  transient network address.
- Crisis matching stores only a boolean and does not automatically escalate priority; support
  contacts remain organizer-controlled configuration.
- Crisis rules are database-backed literal metadata with deterministic normalization; no
  administrator-supplied regex or executable pattern is evaluated.
- Operator content DTOs omit chat, internal notes, track material, and crisis contacts. Admin
  role does not inherit operator triage access.
- Assignment/status/category/priority actions, rejections, and crisis-contact reads use
  allowlisted audit metadata without sensitive free text.
- Access logging is disabled and application logging policy forbids request bodies,
  authorization headers, secrets, and sensitive content.
- Audit metadata is restricted by policy to allowlisted, non-sensitive operational values.
- Staff passwords use Argon2; short-lived access JWTs are bound to revocable server-side
  sessions through a session-ID claim.
- Refresh tokens are high entropy, rotate on use, stay in an HttpOnly cookie, and are stored
  only as keyed HMAC digests. Session records contain no network or device identity.
- Staff login attempts use expiring Valkey counters whose IP/login components are HMAC
  pseudonyms, not raw values.
- Central role guards distinguish unauthenticated (401) from unauthorized (403) requests, and
  the policy boundary explicitly denies sensitive content based on admin role alone.
- Expert reads are additionally constrained by active appeal participation; unrelated experts
  and administrators cannot use expert content endpoints.
- Public chat and internal notes have distinct encrypted records and serializers. Applicant
  responses replace staff identity with a generic specialist label, while operator triage
  serializers do not include applicant-specialist chat.
- Applicant-facing expert writes require an owned, expiring Valkey composer lock, reducing
  conflicting simultaneous specialist responses without storing message content in Valkey.
- Transfer, return, feedback, and complaint free text is encrypted; audit metadata contains
  only safe identifiers and state values.
- A targetless expert reassignment request leaves the current primary responsible until an
  exact-role operator selects an eligible replacement; applicants cannot observe refusal or
  reassignment internals.

## Phase 6A/C7/C8 controls

- Exact-role administrator endpoints expose configuration and operational metadata only; they
  never call content decryption services.
- One-time staff setup/reset links retain only token digests in PostgreSQL and expire by
  default after 24 hours. SMTP secrets remain outside the database and API responses.
- Dynamic form definitions are trusted only after server-side validation; answer values are
  encrypted using the existing intake envelope.
- Stuck-case recovery is row-locked, reasoned, allowlisted to active states, routing/capacity
  checked, historically recorded, and audited without applicant content.
- Audit browsing and CSV/analytics use explicit metadata projections. Regression coverage
  places unique sensitive sentinels in content-like records and verifies they do not appear in
  CSV bytes.
- Compose demo secrets and credentials are explicitly development-only; production settings
  reject the built-in cryptographic defaults. Seed scripts refuse production unless explicitly
  overridden and do not run in normal API startup.

The admin operational reason and safe audit metadata remain a human-input boundary: operators
and administrators must not copy applicant text into those fields. Database access, backup/key
separation, SMTP account security, production TLS/reverse-proxy configuration, and retention
policy still require deployment hardening.

## MVP limitations

Phase 5 adds expert/applicant dialogue, collaboration, and resolution, but not a full
administration or analytics surface. There is no crisis-rule admin UI, malware scanner,
storage retention lifecycle,
backup policy, or deployment TLS configuration. Phrase-based crisis detection can miss novel
wording and can produce false positives; it is not a clinical assessment. Crisis-help contacts
must be approved by organizers before production. Valkey rate limits reduce straightforward
abuse but do not replace proxy-level or distributed abuse controls. A complete key-rotation
and key-custody process is also not implemented.

Otklik does **not** claim network-level anonymity. The application is designed not to persist
or associate client IP addresses or User-Agent values with appeals, but browsers, operating
systems, networks, a future reverse proxy, hosting providers, and other HTTP infrastructure
may transiently observe network metadata. Operational logging and retention must be reviewed
at every deployment boundary.
