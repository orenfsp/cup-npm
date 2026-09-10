# Otklik privacy model

Otklik uses data minimization and separation as its baseline. Anonymous applicants do not
have accounts, user rows, profiles, or durable device identities. The application schema does
not persist applicant names, email addresses, phone numbers, schools, IP addresses,
User-Agent values, device/browser fingerprints, advertising IDs, or analytics identifiers.

## Data separation

The `appeals` table contains operational routing and lifecycle metadata only. Original appeal
text lives in one-to-one `appeal_contents` ciphertext. Sensitive questionnaire data is a
single encrypted payload in `appeal_intake_answers`. Applicant/specialist chat and internal
staff notes are separate encrypted tables so future authorization cannot confuse the two.

The optional crisis contact is the only explicit contact-data exception. It is encrypted in
the isolated `crisis_contacts` table and is available only through a separately authorized,
audited operator endpoint. It must
not be copied into appeal metadata, appeal text, logs, audit metadata, or routing history.

Feedback comments, complaints, applicant return explanations, and expert transfer reasons are
encrypted because free text can contain identifying information. Assignment and status history
retain only safe operational metadata; sensitive explanations are not copied into them.

## Anonymous track access

No raw track number is stored. Lookup normalizes a presented `ОТК-XXXX-XXXX` code in the
application and calculates `HMAC-SHA256(TRACK_HMAC_SECRET, normalized_track_code)`. Only the
32-byte digest is indexed in PostgreSQL. HMAC provides deterministic lookup while preventing
a database-only attacker from directly reading track codes. Ambiguous characters are excluded
from generated codes. A successful check creates a separate, signed, short-lived HttpOnly
cookie scoped to one appeal; it is not an applicant identity and is not accepted as staff
authentication. This does not replace rate limits,
sufficient code entropy, secure delivery, or constant-time authorization behavior.

The separate `RATE_LIMIT_HMAC_SECRET` pseudonymizes transient IP inputs before short-lived
Valkey counters are written for staff login, track checks, and submission. Raw IP values are
not persisted, logged, or associated with appeals. Neither HMAC secret is reused as the
content-encryption key.

## Internal staff authentication

Staff users are an explicit internal identity boundary and are not applicant identities.
Passwords are stored only as Argon2 hashes. Short-lived access JWTs remain in browser memory;
opaque refresh tokens remain in a scoped HttpOnly cookie and are represented in
`staff_sessions` only by a keyed HMAC-SHA256 digest. Session rows contain no IP address,
User-Agent, or device fingerprint. Refresh rotation, logout, account deactivation, and password
changes provide server-side revocation.

Administrative role membership does not imply access to appeal text, applicant-specialist
chat, notes, complaints, or crisis contacts. Expert content reads require an active primary or
coexecutor participant row for that appeal. Operator triage serializers intentionally omit
applicant-specialist chat after assignment. Applicants see only the generic sender label
`Специалист`, never a staff login or display name.

## Encryption boundary

Sensitive fields use AES-256-GCM with a fresh 96-bit random nonce for every encryption. The
binary envelope contains a key-version byte, nonce, and authenticated ciphertext/tag.
Additional Authenticated Data binds content, answers, crisis contacts, rejection explanations,
and attachments
to their record context. Key version 1 is supported now; a key management and rotation workflow is not yet
implemented.

`CONTENT_ENCRYPTION_KEY` is a URL-safe base64 encoding of exactly 32 random bytes. It remains
outside source control. Encryption protects stored content only while keys are kept separate
from the database and its backups; it does not protect plaintext while an authorized process
is actively handling it.

## Attachments and audit records

Attachment records use opaque storage keys and SHA-256 digests. Original filenames and public
URLs are forbidden because filenames commonly contain personal data. Accepted JPEG, PNG, and
WEBP files are decoded, dimension-bounded, orientation-corrected, and re-encoded from pixels so
EXIF/geolocation and unnecessary metadata are removed. Sanitized bytes are AES-GCM encrypted
into private filesystem storage. The stored digest and byte size describe the encrypted blob.
Malware scanning is not yet implemented.

## Crisis handling

Crisis detection is conservative phrase matching over plaintext already in memory for
submission. Only a boolean flag is retained; matched phrases are not logged or stored as new
metadata, and priority remains `standard` until a human changes it. The public help panel is
non-blocking and its contact resources are configuration that organizers must approve before
production. An explicitly supplied crisis contact reduces anonymity and is encrypted only in
the isolated `crisis_contacts` table.

Phase 4 crisis detection loads active literal phrases from `crisis_rules`. Rules are
administrator-managed metadata, never applicant content, and cannot contain executable regex.
Normalization handles Unicode compatibility, case, `ё`/`е`, punctuation, hyphens, and repeated
whitespace. Compact matching is an explicit per-rule choice. Matching retains only the appeal's
boolean crisis flag, never the matched phrase. Phase 6A adds exact-role administrator CRUD
and a transient tester that does not persist or audit tested text.

Operator serializers explicitly enumerate triage fields and omit chat and internal notes.
Administrator role alone does not grant this access. Applicant-visible rejection explanations
are encrypted separately; the text is absent from audit metadata and status-history reasons.
Attachment retrieval verifies the encrypted-blob digest and reveals no private storage path,
storage key, or original filename.

Expert applicant-facing sends require ownership of a short-lived Valkey composer lock. The
lock contains only appeal/staff UUIDs, expires automatically, and is never persisted to
PostgreSQL. Internal notes remain a different encrypted table and API collection from public
chat. Coexecutor/transfer state is staff-only. A `not_helped` resolution stores its explanation
in `appeal_return_explanations`, visible only in authorized operator triage, and is limited to
two returns. Feedback is separate from resolution; encrypted complaints are operator-only.
An expert's targetless “cannot take” request is also stored as an encrypted transfer reason.
It does not change assignment or applicant-visible status until an operator chooses and
approves an eligible replacement; the request is absent from every public serializer.

Audit records may contain allowlisted operational metadata only. Audit `reason` and
`metadata_json` must never contain appeal or chat text, internal notes, crisis contacts,
passwords, access tokens, raw track numbers, or encryption keys. The polymorphic `entity_id`
has no foreign key by design.

## Administration and metadata analytics

The administrator configuration and C7/C8 APIs preserve a strict metadata boundary. Admins
may manage staff/configuration, view workflow identifiers, statuses, priorities, safe assigned
staff metadata, timestamps, aggregate counts, and allowlisted audit events. Those code paths do
not query or decrypt appeal contents, intake values, messages, notes, attachments, crisis
contacts, return explanations, feedback comments, or complaints. Administrator role still does
not satisfy operator/expert content policies.

Stuck-appeal intervention is limited to active workflow states and requires a short operational
reason. Assignment validates active expert role, configured routing eligibility, and capacity;
the transaction writes participant, assignment/status history, and a safe audit event. Terminal
closure/rejection is intentionally unavailable through this recovery control. Operational
reasons must not quote applicant content.

CSV export selects an explicit metadata allowlist from `appeals` and category configuration.
It includes UUID, created timestamp, configured applicant type/category, status, priority,
crisis boolean, timing intervals, and return count. It does not join encrypted tables or expose
track digests. Analytics uses PostgreSQL counts/averages/grouping over the same metadata and
workflow timestamps. Missing metrics are returned as null/empty, never inferred.

Staff invitation/reset tokens use cryptographically secure randomness and are persisted only
as a one-way digest. SMTP credentials remain environment-only. Public applicant types,
questions, and crisis resources are administrator-defined configuration; submitted answers and
optional applicant contact retain their existing encrypted/isolated storage.

## Network and operational limits

The application avoids persisting or associating IP/User-Agent values with appeals, but this
is not a claim of network-level anonymity. HTTP infrastructure may transiently observe IP
addresses and related metadata. Deployment proxy logs, platform logs, backups, staff access,
key custody, and retention settings remain part of the privacy boundary and require explicit
hardening in later phases.
