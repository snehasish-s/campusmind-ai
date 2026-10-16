# Security and privacy design

## Campus work, passport and finance controls

Assignment policies freeze after the first submission. Private work is visible to its student, assignment author and institution administrators. Faculty evidence identifies the reviewer/submission; students cannot promote claims into verification. Passport shares require explicit selection and consent, hashed tokens and expiry. Public output excludes original private work and contact details.

Fee APIs authorize students for their invoices and administrators for institutional billing. Faculty, campus offices and placement officers cannot inspect fee ledgers. Merchant secrets stay backend-only and are bound to an institution UUID. Integer paise, invoice snapshots, callback HMAC, provider capture checks, raw-body webhook HMAC, database locks and unique payment IDs protect accounting. Demo/test/live orders are isolated and test receipts never count as collections. No card, UPI PIN or bank credentials are handled. Refunds, disputes and settlement still require institutional merchant operations and independent review before real money use.

Offline schedules are explicit device opt-in and cleared by logout. The service worker never caches private API responses or share pages. Automated rules cannot invent official notices, grades or fees. See [Campus life and fees](CAMPUS_LIFE_AND_FEES.md) for operational limits.

## Implemented controls

- Institution ownership comes from the authenticated user; CSV/body tenant values never authorize access. Students see their own private records; coordinators are restricted to assigned departments; officers/admins remain institution-scoped.
- Argon2id hashes protect chosen passwords. Opaque session secrets and invitation tokens are stored only as SHA-256 hashes. Session cookies are HTTP-only, host-only, SameSite=Lax and expiring; hosted mode requires Secure/HTTPS.
- Session-bound CSRF headers protect authenticated mutations. JSON authentication/activation and all mutations have origin/fetch-site checks. No cross-origin cookie sharing is configured.
- Single-use activation/reset tokens expire, rotate and revoke older links. Activation consumption is atomic. Password changes end existing sessions. Audited one-time distribution is authorized; active-account manual reset requires an administrator.
- Tokens travel in URL fragments, not server query strings. Private responses use no-store/no-referrer/nosniff. Browser navigation is not treated as authorization.
- Redis limits protect the local distributed configuration, durable database buckets protect hosted mode, and memory limits are explicit single-process development behavior. Redis failure does not silently disable authentication protection.
- Uploads have bounded request/file size, format/content validation, PDF page/encryption/active-action checks, DOCX decompression limits and randomized storage keys. Originals and extracted resume text have separate access-controlled storage. Downloads are attachments.
- Supabase objects remain in a private bucket. The service-role key is backend-only. Supabase client roles have application-table privileges revoked; graph checkpoint schema access is private. Backend tenant checks remain essential even with these public-API restrictions.
- Privileged writes, reads/exports, invitation distribution, role changes, eligibility decisions and approvals have audit records. Logs do not contain raw credentials or invitation links. Workflow/checkpoint output is private and bounded; model/queue failures return safe messages.
- Published question banks require human approval. Active attempts omit correct answers/explanations. Marking uses server snapshots and deadlines. Written/code answers are not executed or automatically used as official subjective grades.
- Model inputs and retrieved files are untrusted data. Structured output is validated, resume qualifications require source support, and eligibility cannot be inferred by the LLM. Source IDs are allowlisted and live permissions rechecked. No unrestricted SQL/shell tool exists.
- Own data export and administrator-reviewed student erasure are implemented. Erasure removes private files, extracted text, claims, attempts, conversations, learning records and related checkpoints. A pseudonymous account ID and privileged audit trail remain for referential integrity. Backup erasure/legal retention is a separate institutional policy.
- `scripts/retention.py` defaults to dry run; `--apply` prunes aged expired credentials, completed import row payloads, workflow/checkpoints and conversations according to `RETENTION_DAYS`. It deliberately does not silently delete institutional source evidence or academic results.
- CSV exports escape leading spreadsheet formula characters. SQLAlchemy queries and parameterized fixed SQL handle sensitive records. Docker infrastructure binds to localhost; application containers run without root.

## Before real institutional deployment

This prototype and its negative tests are not an independent security audit or a compliance certification. Use synthetic records until a responsible institution authorizes a pilot and verifies applicable Indian student-data/privacy requirements.

Required hardening includes an independent threat model and penetration review; separate restricted runtime and migration roles; SSO/MFA and session/device management; malware scanning and document-parser isolation; concurrency/resource-exhaustion tests; restore drills; encryption/key/backup retention policy; formal consent and grievance/correction procedures; accessibility review; dependency monitoring; and incident/support operations with documented ownership.

Hosted free mode does not provide a production availability guarantee. Database row-level tenant policies, if added, must use securely set transaction-local tenant context and cover workers as well as HTTP routes. Do not assume public-API RLS restrictions substitute for service-level tenant checks.

The current taxonomy and assessment evidence thresholds are transparent heuristics. They do not establish broad proficiency, hiring suitability or regulatory compliance. Do not turn coaching indicators into automatic rejection rules.
