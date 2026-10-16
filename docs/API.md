# API guide

FastAPI's live OpenAPI UI is at `http://localhost:8000/docs`. The same-origin browser uses `/api`; the Next.js server proxies those requests to FastAPI. The generated schema is saved in `openapi.json` by `scripts/export_docs.py`.

## Authentication and request protection

`POST /api/auth/login` takes institution code, identifier and chosen password. It returns public account/institution fields and sets an opaque HTTP-only `cm_session` cookie plus a readable `cm_csrf` cookie. Authenticated mutations must include `X-CSRF-Token` with the latter cookie value. Cookies and tenant ownership are resolved on the server; a request body never selects its tenant. Hosted cookies require HTTPS. All record endpoints enforce role and/or ownership.

Activation/reset uses a single-use token from the URL fragment; only its hash is stored. A student must acknowledge the privacy notice during activation. Reissuing an invitation revokes unused older links. Session expiration, logout and password changes invalidate access.

## Main endpoints

| Area | Routes and behavior |
|---|---|
| Auth | `POST /auth/login`, `GET /auth/me`, `POST /auth/logout`, `POST /auth/activate`, `POST /auth/password-reset` |
| Invitations | `POST /auth/invitations/{user_id}/{resend,distribute,revoke}`; privileged, audited and institution-scoped |
| Onboarding | `GET /imports/template`, `POST /imports/preview` multipart file/mapping/policy, `POST /imports/{id}/confirm`, `GET /imports`, `GET /imports/{id}`, `GET /imports/{id}/errors.csv`, `POST /imports/{id}/recover` |
| Students | `GET /students` with search/sort/page/size/department, `GET /students/{id}`, `GET/PUT /profile` |
| Resumes | `GET/POST /resumes`, `GET /resumes/{id}/download`, `GET /resumes/{id}/text`; private owner/officer/authorized coordinator access |
| Companies/drives | `GET/POST /companies`, `GET/POST /drives`, `PUT /drives/{id}`, `GET/POST /drives/{id}/review`, `POST /drives/{id}/transition?status=...`, `/close`, `/apply`, `/view`, `/appeal` |
| Corrections/outcomes | `GET /eligibility-appeals`, `PUT /eligibility-appeals/{id}`, `GET /applications`, `PATCH /applications/{id}?status=...` |
| Skill/preparation | `GET /skills?student_id=...`, `PUT /skills/{id}/review`, `PUT /career-goal`, `GET /matching?drive_id=...&student_id=...`, `GET /resources`, `GET /roadmaps`, `POST /roadmaps/{id}/accept`, `POST /learning-tasks/{id}/complete` |
| Workflows | `POST /workflows`, `GET /workflows`, `GET /workflows/{id}`, `POST /workflows/{id}/retry`, `GET /intelligence/health` |
| Questions/tests | `GET/POST /questions`, `POST /questions/{id}/approve`, `GET/POST /assessments`, `POST /assessments/{id}/start`, `GET /attempts?student_id=...`, `PUT /attempts/{id}/answers?submit=true`, `PUT /attempts/{id}/manual-review` |
| Coach | `GET /coach/conversations`, `POST /coach/chat`; only the authenticated student's authorized records |
| Analytics | `GET /analytics`, `GET /analytics/export.csv`; department, batch, company, drive, assessment, date range, topic, student and search filters |
| Evidence | `GET/POST /evidence/documents`, `POST /evidence/documents/{id}/reindex`, `PUT /evidence/documents/{id}/review`, `DELETE /evidence/documents/{id}`, `POST/GET /evidence/requirements`, `POST /evidence/ask`, `GET /evidence/report.csv` |
| Documents | `GET/POST /documents` compatibility routes; `GET /documents/{id}/download` uses protected local or Supabase storage |
| Administration | `/departments`, `/staff`, `/staff/{id}/access`, `/institution`, `/dashboard`, `/notifications`, `/audit`, `/activity`, `/reports/placement.csv` |
| CollegeOps tasks | `GET/POST /institutional-tasks`, `PUT /institutional-tasks/{id}?status=...`; coordinator submission, administrator approval |
| Privacy | `GET /privacy/export`, `POST /privacy/deletion-request`, `GET /privacy/requests`, `POST /privacy/requests/{id}/erase` with explicit confirmation |
| First setup | `POST /setup`, guarded by a private configured token and absence of existing institutions; UI at `/setup` |

The table omits the common `/api` prefix. Consult OpenAPI for exact fields and allowed values. Validation errors use 422, unauthorized sessions 401, role/CSRF rejection 403, out-of-scope records 404, and lifecycle/conflict errors 409. Transient private storage/queue failures return a safe 503 where handled.

## Assessment contract

Officer-authored questions contain `kind`, `prompt`, `topic`, `difficulty`, `options`, `correct` answer indexes, `points` and `explanation`. They start as drafts. An assessment can only reference approved questions from the officer's institution. Suggested local-model/catalog questions use the same human-approval boundary.

Starting an attempt snapshots approved questions on the server and randomizes their order when configured. Active student responses omit `correct` and `explanation`. Saves use `{"answers":{"QUESTION_ID":[0]}}` for choices or a string for written answers. The deadline is server-owned. A late submission grades previously saved answers; it cannot replace them with late answers. Finalized attempts reveal their own feedback/answer key. Objective score and examiner-reviewed total are separate fields. Code answers are text only.

## Workflow contract

`POST /workflows` accepts an allowlisted `kind`: `resume`, `recruitment`, `gap`, `learning`, `adaptive`, `interview`, `evidence` or `assessment_draft`, plus an appropriate target/question/topic. The server validates role/record scope before dispatch, and the graph rechecks it at execution. The response identifies `id`, `status` and `provider`. Status queries are actor-only. RQ mode returns queued progress; fallback mode runs the same graph synchronously. Retry is bounded to two retries per failed/recoverable run.

Source citations include document ID, title, version, chunk ID and PDF page where available. A model cannot supply an arbitrary document ID to bypass authorization. Draft/missing/expired/rejected/superseded evidence does not become an approved retrieval source.
