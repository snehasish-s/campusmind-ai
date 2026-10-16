# Local intelligence and measured evaluation

## Execution modes

The default mode needs no model, embeddings download or AI API. It uses exact taxonomy mentions, deterministic academic eligibility, evidence-coverage matching, a structured curriculum, exact-set objective marking, and extractive keyword retrieval. The UI and stored records identify these providers explicitly.

`AI_MODE=ollama` enables a LangChain `ChatOllama` provider with Pydantic structured output. Resume claims must include exact source quotes; invented projects and qualifications are discarded. Recruitment extraction cannot change academic eligibility rules. An officer approves the job-skill matrix. Evidence answers render server-owned excerpts, including document version and page when available; the model can select authorized sources but cannot introduce a generated compliance finding. Interview feedback is advisory.

All configured workflows run through a real LangGraph graph with authorization, analysis/validation and persistence nodes, a recursion limit of 8, provider timeouts, bounded retries, an allowlist of workflows and persistent checkpoints. There is no SQL, shell, arbitrary network or document-authorized tool exposed to an LLM. Students can accept roadmap proposals; agents cannot activate plans on their behalf. Heavy local work uses a single RQ AI queue. Structured records and checkpoint threads include tenant/actor identity; checkpoint tables have no public API.

## Enable local models deliberately

Install the lightweight locked API dependencies first. The additional embedding package and weights are opt-in:

```powershell
.\.venv\Scripts\python -m pip install -r services/api/requirements-embeddings.txt
docker compose --profile ai up -d ollama qdrant
docker compose exec ollama ollama pull qwen3:4b
.\.venv\Scripts\python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')"
```

The first model download needs internet and disk space; no paid API or subscription is used. The embedding adapter loads cached weights only during application requests. Select `AI_MODE=ollama` and `EMBEDDING_MODE=sentence_transformers` in `.env`, then restart the API/worker. For a native Python API, Ollama and Qdrant use the localhost URLs; Compose overrides them to container service names. Embedding weights must be installed/cached in the environment running the API/worker, not only on the host. An optional `infra/api-ai.Dockerfile` and Compose override are provided for a container-based embedding worker.

Model size and inference speed depend on your laptop. Start with fallback mode on memory-constrained machines. Do not run large local models inside Render's free web process. Model availability is reported by `/api/intelligence/health`; ordinary workflows remain available if model calls fail.

## Retrieval pipeline

Validated PDF/DOCX/TXT → local extraction → PDF page metadata where available → overlapping chunks → optional Sentence Transformers vectors → Qdrant with tenant/document filters → live database authorization/approval/expiry validation → reciprocal-rank vector/keyword fusion → exact cited excerpts.

Keyword mode is a baseline and a safe fallback when cached models or Qdrant are unavailable. Source documents require administrator approval before retrieval. Reindexing removes old vectors; deletion removes chunks, vector entries and private objects. A missing source produces an explicit insufficient-evidence response. Untrusted document text is never a tool instruction.

## Scoring and adaptation

Preparation alignment uses equal weights for required skills: approved assessment evidence = 1.0; an unverified claim = 0.35; missing evidence = 0.0. The UI labels this evidence coverage and explains the weights. Missing evidence is not a conclusion that the student lacks a skill. Academic eligibility is calculated separately from officer-authored conditions and includes a human correction workflow.

Assessment objective scoring uses exact answer sets, with no partial credit. Written responses and code are never executed and require examiner review. Objective topic evidence requires at least two approved questions and a topic score of at least 70%; this establishes evidence on that question set, not general proficiency certification.

Career goals, skill review, submitted assessments and published drives can propose a new plan. An accepted plan becomes an archived version when a replacement is accepted. Completed work is copied into proposals and checked again on acceptance. Short deadlines produce focused revision tasks with bounded study hours and an explicit warning against interpreting the plan as framework mastery.

## Reproduce evaluation

```powershell
.\.venv\Scripts\python scripts/evaluate.py
.\.venv\Scripts\python -m pytest -q --junitxml=data/backend-results.xml
```

The first command runs a disposable SQLite benchmark and writes `docs/evaluation-results.json`. The second tests real API workflows against isolated synthetic institutions. Neither command uses application records. The versioned labels are in `benchmarks/synthetic-v1.json`.

The recorded benchmark includes ten synthetic resume cases, nine normalization cases, four retrieval queries against three documents, six objective grading cases and three persisted LangGraph runs. Exact measured values and timings are in the JSON file; these tiny cases are sanity checks, not a defensible real-world accuracy estimate. Citation accuracy checks source identity and exact quoted content. Extractive groundedness measures excerpt inclusion; it does not measure the semantic correctness of a generative model or authenticate a source document.

LLM-versus-keyword and real-model vector-versus-hybrid experiments are marked **not run** unless model weights and services have actually been enabled. The Qdrant adapter test uses real in-process Qdrant filtering with controlled test vectors; its passing result is not an embedding-quality benchmark. The benchmark also measures one generic-versus-.NET roadmap scenario using exact unfinished-task skill overlap, study effort and preservation of completed tasks. This is not measured learning improvement; a research claim needs a larger independently labelled evaluation set.

The optional default model is [Qwen3-4B](https://huggingface.co/Qwen/Qwen3-4B), whose official model card identifies Apache-2.0 licensing, using the [Ollama qwen3:4b package](https://ollama.com/library/qwen3:4b). Review the license of any replacement model separately. Thinking mode is disabled for bounded structured calls. No model weights were downloaded or evaluated during the baseline verification.

The optional Compose profile pins [Ollama 0.40.5](https://github.com/ollama/ollama/releases/tag/v0.40.5) and [Qdrant 1.19.2](https://github.com/qdrant/qdrant/releases/tag/v1.19.2), keeping the vector server on the installed client’s 1.19 API family. Cloud execution is disabled in the Ollama container. These manifests were validated; their containers were not run because the local Docker Linux engine was unavailable.

Before a research claim, expand the dataset, separate development/held-out cases, include negation and ambiguous skill statements, measure per-skill errors, use multiple retrieval distractors, annotate citation relevance and unsupported statements independently, and report hardware, model version, cold/warm latency and uncertainty. Never present the small synthetic benchmark as evidence of real placement outcomes.
