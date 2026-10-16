# Feature boundaries

| Area | Implemented behavior | Boundary |
|---|---|---|
| Accounts | Institution-scoped cookies, activation, expiry, RBAC, reset foundations | No SSO/MFA; platform role is still institution-scoped |
| Onboarding | Real validation/persistence, mapping, idempotency and recovery; 1,000-student test | Optional SMTP; audited manual distribution on free Render |
| Resumes | Private versions, extraction, source quotes and student challenge | No OCR; fallback qualifications need labeled source lines |
| Recruitment | Reviewed requirements, lifecycle, academic rules, appeals, applications | No automated hiring decisions or placement probability |
| Skills | Claims, approved assessments and faculty-reviewed assignment evidence remain distinct; expiring consented passports | Fourteen-skill starter taxonomy; evidence is task-specific |
| Campus daily life | Today feed, workload conflicts, targeted official updates, assignments and feedback | Human authorization of official content and subjective grading |
| Campus automation | Idempotent assignment/fee/evidence reminders, browser alerts while open | Free hosting sleeps; background Web Push remains future work |
| Fees | Cohort invoices, local simulator, optional Razorpay checkout, server capture verification, receipts and finance CSV | Merchant setup required for real payments; refunds/settlements need operational procedures |
| Offline/Odia | Installable PWA, opt-in timetable snapshot, optional local translation drafts | Offline mutations unavailable; translation requires staff review |
| Learning | Saved tasks, proposals, accepted/archived versions, preserved completed work | Explicit deterministic curriculum; no mastery/placement guarantee |
| Assessments | Approved questions, timed snapshots, marking and examiner review | No code execution or automatic institutional subjective grading |
| Analytics | Real scores, distributions, matrix, outcomes, progress and CSV | Coaching indicators are not validated risk predictions; load test large cohorts |
| Coach | Own evidence/projects/plans, approved drives, submitted feedback, saved chat | Record-summary fallback; local LLM only for bounded advisory tasks |
| RAG | Real chunks, keyword retrieval, optional embeddings/Qdrant, authorization and citations | No OCR; DOCX/TXT page numbers unavailable; human source adequacy review |
| CollegeOps | Requirement mapping, draft findings, CSV, tasks and human approval | No official certification, signed PDF report or regulatory rule engine |
| Privacy | Consent notice, own export, administrator erasure, retention command | Backups/legal retention require operational policy verification |
| Hosting | Supabase private DB/storage adapter and Render Free blueprint | Credentials blank; no live cloud deployment verification |

## Startup roadmap

1. Independent security, tenant-query, invitation, erasure and backup review before real-data use.
2. Faculty question-bank validation, expanded taxonomy/resources and held-out model evaluation.
3. PostgreSQL/RQ capacity tests, 1,000-plan adaptation benchmarks, upload scanning, restore drills and hosted memory/timeout measurement.
4. Granular permission administration, SSO/MFA, signed PDF exports, accessibility audit and support/incident runbooks.
5. Improve semantic retrieval/advisory generation only after real model comparisons and citation-error analysis.
