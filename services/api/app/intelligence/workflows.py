import hashlib
import re
import time
import secrets
from pathlib import Path
from typing import TypedDict
from contextlib import contextmanager
from sqlalchemy import select
from ..config import settings
from ..db import SessionLocal
from ..models import AIWorkflowRun, User, Resume, ResumeAnalysis, SkillEvidence, RecruitmentDrive, DriveReview, TestQuestion, now
from ..security import scoped, student_access, require, MANAGERS
from .taxonomy import claimed_skills, normalize, TAXONOMY_VERSION
from .contracts import ResumeResult, RecruitmentResult
from .providers import structured, PROMPT_VERSION
from .preparation import skill_record, gap_analysis, propose_roadmap, adapt_after_event
from .events import track


class WorkflowState(TypedDict, total=False):
    run_id: str
    kind: str
    stage: str
    output: dict
    provider: str
    warning: str


@contextmanager
def checkpointer():
    if settings().graph_checkpoint_url.startswith("postgres"):
        from langgraph.checkpoint.postgres import PostgresSaver

        with PostgresSaver.from_conn_string(settings().graph_checkpoint_url) as saver:
            saver.conn.execute("SET search_path TO campusmind_checkpoints")
            saver.setup()
            yield saver
    else:
        from langgraph.checkpoint.sqlite import SqliteSaver

        root = Path(settings().storage_root).resolve().parent
        root.mkdir(parents=True, exist_ok=True)
        with SqliteSaver.from_conn_string(str(root / "graph-checkpoints.db")) as saver:
            yield saver


def extract_resume(text, use_model=True):
    provider, warning = "deterministic_fallback", ""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    fallback = ResumeResult(
        claims=claimed_skills(text),
        projects=[line for line in lines if re.match(r"projects?\s*[:–-]", line, re.I)],
        internships=[line for line in lines if re.match(r"internships?\s*[:–-]", line, re.I)],
        certifications=[line for line in lines if re.match(r"certifications?\s*[:–-]", line, re.I)],
        limitations=[
            "Mentions are claims, not proficiency. Fallback project/qualification extraction requires a labeled source line and student review."
        ],
    )
    result = fallback
    if use_model and settings().ai_mode == "ollama":
        for _ in range(2):
            try:
                result = structured(
                    "Extract only skills and qualifications directly supported by exact quotes. Use taxonomy: "
                    + ", ".join(normalize(c["skill"]) for c in claimed_skills(text)),
                    text,
                    ResumeResult,
                )
                provider = "ollama:" + settings().ollama_model
                break
            except Exception:
                warning = "Local model unavailable or invalid output; exact keyword extraction was used."
    # A model cannot create an unsupported claim or fabricate a project/certification.
    result.claims = [
        c.model_copy(update={"skill": normalize(c.skill)})
        for c in result.claims
        if normalize(c.skill)
        and c.quote.strip().casefold() in text.casefold()
        and any(x["skill"] == normalize(c.skill) for x in claimed_skills(c.quote))
    ]
    for field in ("projects", "internships", "certifications"):
        setattr(result, field, [v for v in getattr(result, field) if v.strip() and v.casefold() in text.casefold()])
    return {
        **result.model_dump(),
        "provider": provider,
        "warning": warning,
        "taxonomy_version": TAXONOMY_VERSION,
        "prompt_version": PROMPT_VERSION,
    }


def extract_recruitment(drive):
    text = drive.description + "\n" + drive.additional_requirements
    detected = claimed_skills(text)
    skills = []
    for item in detected:
        quote = item["quote"]
        priority = (
            "preferred"
            if re.search(r"preferred|nice.to.have|optional", quote, re.I)
            else "required"
            if re.search(r"required|must|mandatory|essential", quote, re.I)
            else "unclear"
        )
        skills.append({"skill": item["skill"], "priority": priority, "quote": quote})
    result = RecruitmentResult(
        skills=skills,
        responsibilities=[line.strip() for line in text.splitlines() if re.search(r"develop|build|design|maintain|responsib", line, re.I)][
            :10
        ],
        stated_conditions=[line.strip() for line in text.splitlines() if re.search(r"cgpa|backlog|batch|graduat|branch", line, re.I)][:10],
        ambiguities=["Officer must confirm all required/preferred skills and explicitly stated academic conditions before publication."],
    )
    provider = "deterministic_fallback"
    if settings().ai_mode == "ollama":
        try:
            candidate = structured(
                "Extract stated role requirements with exact quotes. Do not invent eligibility. Use controlled taxonomy. Unclear priority must remain unclear.",
                text,
                RecruitmentResult,
            )
            candidate.skills = [s for s in candidate.skills if normalize(s.skill) and s.quote.casefold() in text.casefold()]
            candidate.responsibilities = [v for v in candidate.responsibilities if v.casefold() in text.casefold()]
            candidate.stated_conditions = [v for v in candidate.stated_conditions if v.casefold() in text.casefold()]
            result, provider = candidate, "ollama:" + settings().ollama_model
        except Exception:
            pass
    return {
        **result.model_dump(),
        "provider": provider,
        "prompt_version": PROMPT_VERSION,
        "source_hash": hashlib.sha256(text.encode()).hexdigest(),
    }


def execute_run(run_id):
    from langgraph.graph import StateGraph, START, END
    from langsmith import tracing_context

    started = time.perf_counter()
    with SessionLocal() as db:
        run = db.scalar(select(AIWorkflowRun).where(AIWorkflowRun.id == run_id).with_for_update())
        if not run or run.status not in {"queued", "failed"}:
            return
        actor = db.get(User, run.payload["actor_id"])
        if not actor or not actor.active or actor.institution_id != run.institution_id:
            run.status = "failed"
            run.payload = {**run.payload, "error": "Actor is no longer authorized."}
            db.commit()
            return
        kind, target = run.payload["kind"], run.payload.get("target_id")
        run.status = "running"
        lease = secrets.token_hex(16)
        run.payload = {**run.payload, "started_at": now().isoformat(), "lease": lease}
        from rq import get_current_job

        rq_job = get_current_job()
        if rq_job:
            rq_job.meta["lease"] = lease
            rq_job.save_meta()
        db.commit()

        def authorize(state):
            if kind == "resume":
                resume = scoped(db, Resume, actor, target)
                student_access(db, actor, resume.user_id)
            elif kind == "recruitment":
                require(actor, MANAGERS)
                scoped(db, RecruitmentDrive, actor, target)
            elif kind == "assessment_draft":
                require(actor, MANAGERS)
            elif kind in {"gap", "learning", "adaptive", "interview"}:
                require(actor, {"student"})
                if target:
                    drive = scoped(db, RecruitmentDrive, actor, target)
                    if drive.status in {"draft", "reviewed"}:
                        raise ValueError("Drive is not published")
            elif kind == "evidence":
                require(actor, {"institution_admin", "platform_admin", "hod"})
            else:
                raise ValueError("Workflow is not allowlisted")
            return {"stage": "authorized"}

        def analyze(state):
            if kind == "resume":
                resume = scoped(db, Resume, actor, target)
                from ..storage import get_storage

                output = extract_resume(get_storage().read(resume.text_key).decode("utf-8"))
            elif kind == "recruitment":
                output = extract_recruitment(scoped(db, RecruitmentDrive, actor, target))
            elif kind == "assessment_draft":
                from .question_drafts import draft_questions

                output = draft_questions(run.payload.get("topic", "SQL"), run.payload.get("count", 2))
            elif kind in {"gap", "learning", "adaptive"}:
                drive = scoped(db, RecruitmentDrive, actor, target) if target else None
                output = gap_analysis(db, actor, drive)
                if kind != "gap":
                    plan = propose_roadmap(db, actor, drive, run.payload.get("trigger", "student_request"))
                    output = {"roadmap_id": plan.id, "explanation": plan.payload["explanation"]}
                output["provider"] = "deterministic_fallback"
            elif kind == "evidence":
                from .retrieval import answer_evidence

                output = answer_evidence(db, actor, run.payload.get("question", ""))
            else:
                from .coach import interview_feedback

                output = interview_feedback(db, actor, run.payload.get("question", ""), run.payload.get("answer", ""))
            return {"output": output, "provider": output.get("provider", "deterministic_fallback"), "stage": "validated"}

        def persist(state):
            output = state["output"]
            if kind == "resume":
                resume = scoped(db, Resume, actor, target)
                analysis = ResumeAnalysis(institution_id=actor.institution_id, resume_id=resume.id, payload=output)
                db.add(analysis)
                db.flush()
                existing = list(db.scalars(select(SkillEvidence).where(SkillEvidence.user_id == resume.user_id)))
                for claim in output["claims"]:
                    if any(e.payload.get("resume_id") == resume.id and e.payload.get("skill") == claim["skill"] for e in existing):
                        continue
                    skill = skill_record(db, actor.institution_id, claim["skill"])
                    db.add(
                        SkillEvidence(
                            institution_id=actor.institution_id,
                            user_id=resume.user_id,
                            skill_id=skill.id,
                            payload={
                                **claim,
                                "status": "pending_review",
                                "resume_id": resume.id,
                                "analysis_id": analysis.id,
                                "provider": state["provider"],
                            },
                        )
                    )
                track(db, actor, "resume.analyzed", "Resume evidence extracted", resume_id=resume.id)
                db.flush()
                adapt_after_event(db, db.get(User, resume.user_id), "resume_evidence_changed")
            elif kind == "recruitment":
                review = db.scalar(select(DriveReview).where(DriveReview.drive_id == target))
                if not review:
                    review = DriveReview(institution_id=actor.institution_id, drive_id=target)
                    db.add(review)
                review.payload = {**(review.payload or {}), "extracted": output}
            elif kind == "assessment_draft":
                from .assessments import QuestionInput

                for raw in output["questions"]:
                    validated = QuestionInput.model_validate(raw)
                    db.add(
                        TestQuestion(
                            institution_id=actor.institution_id,
                            payload={
                                **validated.model_dump(),
                                "status": "draft",
                                "created_by": actor.id,
                                "provenance": state["provider"],
                                "workflow_id": run.id,
                            },
                        )
                    )
                from ..security import audit

                audit(db, actor, "assessment.drafts", run.id, {"question_count": len(output["questions"]), "provider": state["provider"]})
            run.status = "completed"
            run.provider = state["provider"]
            run.payload = {
                **run.payload,
                "result": output,
                "prompt_version": PROMPT_VERSION,
                "latency_ms": round((time.perf_counter() - started) * 1000),
                "stages": ["authorized", "validated", "persisted"],
            }
            db.commit()
            return {"stage": "persisted"}

        graph = StateGraph(WorkflowState)
        graph.add_node("authorize", authorize)
        graph.add_node("analyze", analyze)
        graph.add_node("persist", persist)
        graph.add_edge(START, "authorize")
        graph.add_edge("authorize", "analyze")
        graph.add_edge("analyze", "persist")
        graph.add_edge("persist", END)
        try:
            with checkpointer() as saver, tracing_context(enabled=False):
                graph.compile(checkpointer=saver).invoke(
                    {"run_id": run.id, "kind": kind},
                    {"configurable": {"thread_id": f"{actor.institution_id}:{actor.id}:{run.id}"}, "recursion_limit": 8},
                )
        except Exception:
            db.rollback()
            run = db.get(AIWorkflowRun, run_id)
            run.status = "failed"
            run.payload = {
                **run.payload,
                "error": "Workflow could not complete safely. Check local provider/storage availability and retry.",
                "latency_ms": round((time.perf_counter() - started) * 1000),
            }
            db.commit()


def dispatch(db, actor, kind, target_id=None, **inputs):
    run = AIWorkflowRun(
        institution_id=actor.institution_id,
        status="queued",
        provider="pending",
        payload={"actor_id": actor.id, "kind": kind, "target_id": target_id, **inputs},
    )
    db.add(run)
    db.commit()
    if settings().queue_mode == "rq":
        from rq import Queue
        from redis import Redis

        try:
            from rq.job import Callback

            Queue("campusmind-ai", connection=Redis.from_url(settings().redis_url)).enqueue(
                execute_run, run.id, job_timeout=180, on_failure=Callback(mark_workflow_failed, timeout=30)
            )
        except Exception:
            run.status = "failed"
            run.payload = {**run.payload, "error": "AI queue is unavailable."}
            db.commit()
    else:
        execute_run(run.id)
        db.refresh(run)
    return run


def mark_workflow_failed(rq_job, connection, *exc_info):
    with SessionLocal() as db:
        run = db.get(AIWorkflowRun, rq_job.args[0])
        if run and run.status != "completed" and rq_job.meta.get("lease") == run.payload.get("lease"):
            run.status = "failed"
            run.payload = {**run.payload, "error": "The background workflow stopped or exceeded its time limit. You can retry it."}
            db.commit()
