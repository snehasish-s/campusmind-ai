# CampusMind AI

CampusMind CollegeOps + PlacementOS is an implemented local-first Next.js/FastAPI application with institution-scoped records, bulk onboarding, resumes, recruitment, approved assessments, preparation roadmaps and an institutional evidence assistant. All demonstration records are synthetic. No paid AI API or software subscription is required.

The existing Phase 1 application has been extended incrementally. Supabase PostgreSQL/private Storage and Render Free deployment files are included; **no cloud account has been connected or deployed**. Insert credentials privately using [the hosted worksheet](.env.hosted.example) and [deployment guide](docs/DEPLOYMENT.md).

## Run locally without Docker or an LLM

Prerequisites: Python 3.13, Node.js 22.19+, and internet for initial dependency installation. From this repository folder:

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r services/api/requirements.lock.txt
.\.venv\Scripts\python scripts/setup_env.py --sqlite
$env:PYTHONPATH = 'services/api'
.\.venv\Scripts\python -m alembic -c services/api/alembic.ini upgrade head
.\.venv\Scripts\python scripts/seed.py --choose-admin-password
.\.venv\Scripts\python scripts/seed_learning.py
.\.venv\Scripts\python scripts/generate_students.py
cd apps/web
npm ci
cd ../..
.\.venv\Scripts\python scripts/dev.py
```

If `.env` or `.venv` already exists, preserve it and skip its creation. The setup script refuses to overwrite `.env`. Local fallback uses SQLite, synchronous processing and memory rate limits. It is a development mode; PostgreSQL/Docker exercises different infrastructure.

Open [CampusMind](http://localhost:3000), [API documentation](http://localhost:8000/docs) or [health](http://localhost:8000/api/health). Linux/macOS use `.venv/bin/python` and `export PYTHONPATH=services/api`.

**Login setup:** institution code `demo`, administrator ID `ADMIN`, placement officer ID `PLACEMENT`. Choose the admin password when prompted. The seed prints a separate random officer password once; save it securely. There is no common/default password in source. Rerunning the seed does not reset credentials.

Upload `data/synthetic-students.csv` from Bulk student import. Review mapping and preview, then confirm. Open a pending student in Student registry and select **One-time distribution** to issue an audited activation link when Mailpit is unavailable. The student opens it, acknowledges the privacy notice, chooses a password and signs in with their own roll number. Tokens are short-lived, single-use and stored only as hashes.

## Full local infrastructure

Docker Desktop's Linux engine must be running. Generate `.env` with `scripts/setup_env.py` without `--sqlite` for a new Docker-only installation, then:

```powershell
docker compose up --build -d
docker compose run --rm api python scripts/seed.py --choose-admin-password
docker compose run --rm api python scripts/seed_learning.py
```

Compose supplies PostgreSQL, Redis, RQ, Mailpit, FastAPI and Next.js. It overrides host connection URLs automatically. Data persists in local volumes. Mailpit is at [localhost:8025](http://localhost:8025), so synthetic activation emails never need a real mailbox. Stop with `docker compose down`; `down -v` deletes database/upload volumes and is not a routine shutdown command.

Ollama and Qdrant are opt-in under the `ai` profile. See [AI setup and evaluation](docs/AI_AND_EVALUATION.md), including optional embedding-model downloads and the heavier container override. Core workflows remain useful without those services.

## Implemented workflows

- Tenant-scoped admin, placement officer, HOD/coordinator and student access; Argon2id passwords; HTTP-only sessions; CSRF/origin protection; logout; expiration; invitation rotation and reset foundations.
- CSV template, mapping, normalization, row validation, duplicates, skip/update policy, preview, 100-row transactions, progress, history, error downloads, idempotency and expired-job recovery. Limit: 20,000 records / 8 MB; the 1,000-student flow is tested.
- Editable academic/contact profiles, projects/internships, private PDF/DOCX resume versions and separately stored extracted text. Students confirm, challenge or reject extracted claims.
- Real LangGraph authorization, analysis/validation and persistence; optional LangChain/Ollama structured output; bounded model calls; persistent checkpoints; workflow history, retries and provider provenance.
- Controlled skill taxonomy, claimed versus assessment-demonstrated evidence, explainable preparation alignment, objective eligibility and officer-reviewed corrections.
- Draft/review/publish/open/close/complete recruitment lifecycle. Officer-authored publication records human approval. Extracted requirements require review. Drives create targeted notices and propose adaptations for active student plans.
- Saved, versioned learning tasks with free resources, study-hour budgets, realistic short-deadline revision, student acceptance and preserved completed tasks.
- Approved question bank; single/multiple MCQs; subjective/code/interview exercises; timed persisted attempts; server marking; topic results; history and examiner review. Student code is never executed. Suggested questions remain drafts until approved.
- Stored-result analytics, score distributions, topic charts, evidence matrix, student drill-down, learning progress, application outcomes and authorized CSV export.
- Private career-coach conversations using personal evidence, project context, approved drives and submitted-test feedback; unscored interview practice and optional local advisory feedback.
- CollegeOps PDF/DOCX/TXT upload, deduplication, versions, department/owner metadata, expiry, indexing, approval, configurable requirements, source-linked answers and draft CSV reports. Institutional tasks support coordinator submission and administrator approval.
- Own data export, administrator-reviewed student erasure, pseudonymous audit retention and explicit retention maintenance.
- Responsive navy/blue/teal interface, dark theme, accessible forms, Motion transitions, reduced-motion support and mobile navigation.

## Verification

Actual execution and boundaries are recorded in [VERIFICATION.md](docs/VERIFICATION.md). Reproduce checks with:

```powershell
.\.venv\Scripts\python -m pytest -q --junitxml=data/backend-results.xml
.\.venv\Scripts\python -m ruff check services scripts tests
.\.venv\Scripts\python -m alembic -c services/api/alembic.ini check
.\.venv\Scripts\python scripts/evaluate.py
cd apps/web
npm run lint
npm run typecheck
npm run build
$env:CM_BROWSER_PATH = 'C:/Program Files/Google/Chrome/Application/chrome.exe'
npm run test:e2e
```

Browser tests require API port 8000 and web port 3000. Their setup creates a distinct synthetic institution with random test passwords. Use `npx playwright install chromium` if local Chrome is unavailable. The benchmark saves actual values to `docs/evaluation-results.json`; optional experiments are explicitly marked when not run.

## Project layout

```text
apps/web/                 App Router, typed client, dashboards, browser tests
services/api/app/          Routes, authorization, storage, SQLAlchemy models
services/api/app/intelligence/
                          LangGraph, providers, taxonomy, plans, tests, retrieval
services/api/migrations/   Incremental Alembic migrations
services/worker/          RQ import and AI worker
infra/                    Local/AI/Render containers and startup supervisor
scripts/                  Setup, seeds/CSV, launcher, evaluation, retention
tests/                   Backend integration, security and adapter tests
benchmarks/               Versioned synthetic labels
docs/                     Architecture, API, diagrams, evaluation, demo, deployment
docker-compose.yml        Local stack; optional docker-compose.ai.yml
render.yaml               Single free web-service blueprint
.env.hosted.example       Private credential insertion worksheet
```

## Handover

- [Architecture and diagrams](docs/ARCHITECTURE.md)
- [API guide](docs/API.md)
- [Demonstration scenarios A–F](docs/DEMO.md)
- [AI methodology and evaluation](docs/AI_AND_EVALUATION.md)
- [Actual measured findings](docs/EVALUATION_FINDINGS.md)
- [Database ER and workflow diagrams](docs/DIAGRAMS.md)
- [Supabase/Render instructions](docs/DEPLOYMENT.md)
- [Security and hardening](docs/SECURITY.md)
- [Feature boundaries and future roadmap](docs/FEATURES.md)

This is a synthetic-data pilot prototype. Real institutional deployment needs independent security review, verification of applicable Indian privacy obligations, backup/restore and retention procedures, concurrency/load tests, accessibility review and support operations. Free infrastructure has quotas and availability limits. Local model quality and live cloud deployment are not established by deterministic fallback tests.


## Campus Hub: whole-college communication

Campus Hub now supports targeted department/leadership notices, teacher assignments, private attachments, read acknowledgements and CSV/XLSX cohort/timetable imports. New least-privilege staff roles: `faculty` and `campus_staff`. Open `/app/campus` and `/app/timetable`. See [Campus Hub setup and CSV templates](docs/CAMPUS_HUB.md). Apply the latest Alembic migration before restarting existing installations.
