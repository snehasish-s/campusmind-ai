# Campus life and fee management

This extension retains the Next.js/FastAPI architecture, database, authorization and private local/Supabase storage. Nine new tables support real academic, communication and finance workflows. All features work without an LLM; local payment demonstrations need no gateway account.

## Upgrade and demonstration

Preserve existing `.env` credentials. From the repository root:

```powershell
$env:PYTHONPATH = 'services/api'
.\.venv\Scripts\python -m alembic -c services/api/alembic.ini upgrade head
.\.venv\Scripts\python scripts/seed_campus.py
.\.venv\Scripts\python scripts/dev.py
```

The optional seed requires the fictional `demo` institution from `scripts/seed.py`. It creates `CAMPUSSTUDENT` and `TEACHER001` with separate random passwords displayed once, a timetable, an SQL assignment and a demo invoice. It never resets passwords. For Render, deploy the updated repository with the existing Dockerfile; startup applies migrations. Public PWA assets are included in the image.

| Page | Authorized users | Working features |
|---|---|---|
| `/app/today` | All student years | Classes, assignment and fee deadlines, unread updates, workload/schedule warnings. Placement-eligible years also see assessments, drives and learning tasks. |
| `/app/assignments` | Students, authors and administrators | Private versioned work, attachments, rubric marks, feedback, revision and faculty skill verification. |
| `/app/passport` | Students | Claim/assessment/faculty evidence, selected consented shares, revocation and own privacy activity. |
| `/app/fees` | Students and administrators | Own invoices, payment confirmation, verified receipts; administrator cohort billing, search, CSV ledger and reconciliation. |
| `/app/automations` | Administrators | Configurable reminder categories, delivery activity and an audited manual sweep. |
| `/app/evidence-map` | Administrators and HODs | Scoped requirement-to-document relationships, review states, owners, expiry and versions. |

Campus Hub is independent of PlacementOS. First/second-year students can submit work, build passports and use fees; PlacementOS remains limited to third/fourth year. Publishing authority still comes from authorized offices and valid teaching rosters.

## Assignment-to-skill workflow

Publish an assignment to an exact cohort. Before submissions, configure unique rubric criteria totalling 100 marks, controlled taxonomy skills and optional late work. Students submit text or checked PDF/DOCX/TXT documents; versions and rubric snapshots are preserved. Only the author/admin reviews the latest version. Returned work can be revised after the original deadline.

Explicit faculty verification requires at least 60/100 and mapped skills. Evidence identifies the submission, reviewer and score. Correcting a review supersedes earlier evidence. Students cannot edit verified evidence as a resume claim. Verified faculty work contributes to the transparent preparation alignment formula and proposes updates to existing accepted placement roadmaps. Student acceptance remains required. No code is executed or subjective work automatically graded.

## Automatic communication

Posts, timetable/cohort changes and existing drive events notify recipients in-app. No WhatsApp forwarding is needed. Read acknowledgement remains explicit; it never proves device delivery.

While the API runs, a 60-second loop checks institutional reminders behind a durable 15-minute sweep gate. PostgreSQL locks and unique `(institution, event, recipient)` records prevent duplicate delivery. Configurable rules include:

- Unsubmitted/returned assignment: once within 24 hours of the deadline.
- Unpaid fees: once at each 7-day, 3-day, 1-day and overdue stage.
- Evidence renewal: once within 7 days of expiry and once after expiry, to its owner.

`python scripts/run_reminders.py` supports scheduled local or always-on worker execution. Render Free sleeps; exact wall-clock reminders cannot be guaranteed while asleep. The loop and student Today requests catch up after wake-up. Browser notifications require explicit permission and opt-in, operate while the app is open, and hide academic/financial details in their bodies. Background Web Push is not implemented.

## Payment configuration

Defaults require no payment or subscription:

```dotenv
AUTOMATION_ENABLED=true
AUTOMATION_INTERVAL_SECONDS=60
PAYMENT_PROVIDER=demo
RAZORPAY_KEY_ID=
RAZORPAY_KEY_SECRET=
RAZORPAY_WEBHOOK_SECRET=
PAYMENT_INSTITUTION_ID=
```

The local simulator records `demo_paid`, creates a clearly labelled `TEST-` receipt and collects no money. It never contributes to real collection totals.

For optional Razorpay checkout, enter these only in the backend's private environment:

```dotenv
PAYMENT_PROVIDER=razorpay
RAZORPAY_KEY_ID=YOUR_TEST_OR_LIVE_KEY_ID
RAZORPAY_KEY_SECRET=YOUR_PRIVATE_KEY_SECRET
RAZORPAY_WEBHOOK_SECRET=YOUR_SEPARATE_WEBHOOK_SECRET
PAYMENT_INSTITUTION_ID=YOUR_INSTITUTION_UUID
```

Find the institution UUID in the authenticated admin's `/api/auth/me` response. It is not the college slug. One merchant is bound to one institution; other colleges cannot collect into that merchant account. Multiple merchants require dedicated deployments or a future encrypted per-tenant credential service.

Configure a `payment.captured` webhook at `https://YOUR_HOST/api/campus/fees/webhook`, with the matching separate webhook secret. Enable automatic capture in the merchant dashboard and start with test keys. Gateway test payments also remain `demo_paid` and never count as real collections.

Controls include administrator-set integer paise amounts, audience preview, immutable issued invoice amounts and unique billing references. Separate plans can represent instalments. Payment always requires student initiation. Orders are created server-side; browser callbacks require HMAC plus a server fetch confirming captured status, original order, amount and INR currency. Raw webhook bytes require HMAC. Database locks and event/payment uniqueness make retries idempotent. Demo/test/live orders are isolated. Status refresh recovers delayed callbacks. An uncertain order creation blocks another charge until finance verifies its merchant receipt. Receipts, voids, exports and reconciliation are audited. No card number, CVV, UPI PIN or bank credential is stored.

Development/demo cost is ₹0. Live payments require institutional merchant onboarding and applicable transaction fees: [pricing](https://razorpay.com/pricing/), [test/live modes](https://razorpay.com/docs/payments/dashboard/test-live-modes/), [integration](https://razorpay.com/docs/payments/payment-gateway/web-integration/standard/integration-steps/). No actual merchant has been connected or charged by this implementation. Automated gateway tests mock provider transport and verify security/business logic.

## Privacy, accessibility and offline operation

Passport tokens are random and stored as hashes. Students select evidence, explicitly consent and choose 1–168-hour expiry. Public output contains their name and selected evidence type/status, skill, score and date; resume text, work, contact details and registration number are excluded. Revocation is immediate and access is audited. Anyone holding the link can view it until expiry/revocation.

The PWA caches a public offline shell and immutable static assets, never API data or passport links. Students may explicitly save a timetable snapshot on their device and delete it from `/offline`; logout removes it. Offline schedules are labelled stale. Payments, submissions and current notices require connectivity; offline mutation sync is not implemented.

Odia can be entered directly. Optional bounded Ollama translation drafts require staff review before being appended to an official message. Without a local model, manual bilingual entry remains available; there is no invented translation or automatic publication.

Own export includes work and invoices. Approved erasure deletes private work/files and shares. Accounting records stay linked to a pseudonymous account for reconciliation; the institution must verify legal retention requirements. Privacy activity exposes recorded profile/resume/passport access to the student.

## Pilot boundaries

Staff must authorize notices and fee amounts, judge subjective work and handle disputes. Students initiate payments and consent to sharing. Automation removes repetitive distribution and deadline forwarding, not institutional accountability.

Before real fee collection, strengthen refunds/chargebacks/settlement reconciliation, concessions and scholarships, partial balances, legal receipt review, per-tenant merchant secrets, independent security/privacy review and PostgreSQL concurrency/load testing. Continuous hosting is needed for uninterrupted reminders. Attendance, automatic semester promotion and background push remain future work. Actual merchant test-mode, refund and live settlement validation require an authorized account.
