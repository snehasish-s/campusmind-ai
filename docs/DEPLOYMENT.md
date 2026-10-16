# Supabase Free + Render Free

Credentials are intentionally blank. Nothing has been connected to your accounts or deployed. Use `.env.hosted.example` as a worksheet and enter values in Render's **Environment** settings. Never send database passwords or service-role keys through chat or put them in a browser variable.

Your current workspace also has `.env.hosted.local`, a private, ignored copy with insertion spaces. Fill that copy rather than putting real credentials into the tracked example. It is a worksheet for Render's environment, not a configuration automatically loaded by the local application. On a fresh clone, copy the example to `.env.hosted.local` first. Both Git and Docker ignore private `.env.*` files.

## Prepare Supabase

1. Use a dedicated free Supabase project for synthetic CampusMind data.
2. In **Connect**, copy the **Session pooler** connection string. Keep the displayed pooler hostname and username exactly as Supabase supplies them. URL-encode special characters in the database password. Use port **5432**, not the transaction pooler port, for graph checkpoints and migrations.
3. Set `DATABASE_URL` with the `postgresql+psycopg://` prefix and `?sslmode=require`. Set `GRAPH_CHECKPOINT_URL` to the same credentials with the ordinary `postgresql://` prefix. These are two syntax forms for the same database; do not create two databases.
4. In Storage, create a **private** bucket called `campusmind-private`. Set an 8 MB object limit. Keep it private and do not create public read policies. The API downloads objects after authorizing the request.
5. Copy the project URL and backend service-role key into the corresponding private Render environment fields. Do not use an anonymous/publishable key for private server storage. Do not prefix secrets with `NEXT_PUBLIC_`.

The migrations revoke application-table access from Supabase's `anon` and `authenticated` roles and enable RLS without public policies. Application sessions remain CampusMind HTTP-only cookies; Supabase Auth is not a second login system. LangGraph checkpoints use a private, unexposed schema. Use a dedicated database project: the initial connection generally has migration-owner privileges. Separating an operator migration role from a restricted runtime role is a required pilot hardening step.

Supabase documents [connection choices](https://supabase.com/docs/guides/database/connecting-to-postgres) and [private bucket creation](https://supabase.com/docs/guides/storage/buckets/creating-buckets). Check the dashboard's current free quota before uploading large datasets.

## Prepare Render

1. Push this existing repository to your own GitHub repository. Keep `.env` and `data/` excluded. If the repository root is the parent folder, set Render's root directory to `campusmind-ai`.
2. Create a Blueprint using `render.yaml`, or a Docker Web Service using `infra/render.Dockerfile`. Choose **Free**. No paid database or background worker is declared.
3. Enter each `sync: false` field from the worksheet. Set `APP_ORIGIN` to your actual `https://SERVICE.onrender.com` address with no trailing slash. Leave `SECURE_COOKIES=true`.
4. Deploy. Startup applies Alembic migrations, runs FastAPI on private loopback port 8000 and serves Next.js on Render's `PORT`. Same-origin `/api` proxying preserves cookie and CSRF behavior.
5. Open `/setup`, enter the generated private `BOOTSTRAP_TOKEN`, choose an administrator password and create the first institution. This endpoint refuses a second setup after an institution exists. Remove `BOOTSTRAP_TOKEN` from Render afterward. Never use a shared demo password.
6. Sign in with your chosen institution code and `ADMIN`. Create departments and invite a placement officer through Staff & roles. Use **One-time distribution** in the registry when email is unavailable.

This deployment uses persistent PostgreSQL sessions, jobs, assessments, roadmaps and rate-limit buckets; private Supabase object storage; PostgreSQL graph checkpoints; synchronous processing; keyword evidence retrieval; and clearly labelled deterministic preparation. Local model weights, Redis and Qdrant are not required on Render.

## Free-service limits

Render's [free-service documentation](https://render.com/docs/free) describes idle spin-down, ephemeral local files, monthly usage quotas and blocked SMTP ports. A single web service shares its small memory allocation between Next.js and FastAPI. Large imports and many concurrent users require measured capacity planning. Free hosted mode is a demonstration deployment, not an institutional production SLA. Source documents and records live outside Render's ephemeral filesystem.

RQ workers and local AI run in the local Docker setup. On the free host, imports are synchronous and may exceed an HTTP proxy timeout on slow connections. Persisted batch checkpoints allow a failed import to resume. If a process is terminated mid-job, use the authenticated job recovery action after its lease expires. Do not switch to a paid service merely to complete this demo. Keep development fully local when free quotas or account restrictions prevent deployment.

## Credential worksheet

| Field | Insert privately |
|---|---|
| `DATABASE_URL` | Supabase session pooler URL with `postgresql+psycopg://` |
| `GRAPH_CHECKPOINT_URL` | Same session pooler with `postgresql://` |
| `SUPABASE_URL` | `https://YOUR_PROJECT_REF.supabase.co` |
| `SUPABASE_SERVICE_ROLE_KEY` | Backend-only service-role key |
| `SUPABASE_STORAGE_BUCKET` | `campusmind-private` |
| `APP_ORIGIN` | Actual Render HTTPS app address |
| `BOOTSTRAP_TOKEN` | Random setup secret, at least 32 characters; remove after setup |

`.env.hosted.example` contains these exact insertion spaces. There are no credentials committed in this project.
