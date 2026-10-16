# Phase 2 integration record

The existing Next.js/FastAPI/SQLAlchemy application was extended in place. No replacement project or paid AI service was introduced.

Modules under `services/api/app/intelligence/` connect to existing workspace routes. Accounts, bulk onboarding, resumes, drives, departments, staff and audits remain the foundation. Incremental migrations add review, evidence, conversations, career goals, tasks, durable rate limits and processing leases.

Resume, recruitment, gap, learning/adaptive, interview, draft-question and evidence workflows use bounded LangGraph stages and persistent checkpoints. LangChain/Ollama and Sentence Transformers/Qdrant are optional adapters. Clearly labelled deterministic providers remain usable locally and on lightweight hosted infrastructure.

See FEATURES.md for boundaries, AI_AND_EVALUATION.md for methodology, VERIFICATION.md for execution evidence, DEPLOYMENT.md for credential fields and DEMO.md for scenarios A–F. Optional model/cloud verification must not be inferred from fallback tests.
