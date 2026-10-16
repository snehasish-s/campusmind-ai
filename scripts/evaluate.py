"""Measured synthetic evaluation in a disposable database; never touches application data."""

import json
import os
import statistics
import sys
import tempfile
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services/api"))
temporary = tempfile.TemporaryDirectory(prefix="campusmind-evaluation-")
os.environ.update(
    DATABASE_URL="sqlite:///" + str(Path(temporary.name) / "evaluation.db"),
    STORAGE_ROOT=str(Path(temporary.name) / "storage"),
    QUEUE_MODE="sync",
    RATE_LIMIT_BACKEND="memory",
    DEPLOYMENT_MODE="local",
    GRAPH_CHECKPOINT_URL="",
    AI_MODE="fallback",
    EMBEDDING_MODE="keyword",
    STORAGE_BACKEND="local",
)
from app.db import Base, engine, SessionLocal  # noqa: E402
from app.models import Institution, User, Resume, InstitutionalDocument, CareerGoal, Company, RecruitmentDrive, LearningTask, now  # noqa: E402
from app.storage import get_storage  # noqa: E402
from app.intelligence.workflows import extract_resume, dispatch  # noqa: E402
from app.intelligence.taxonomy import normalize  # noqa: E402
from app.intelligence.retrieval import index_document, retrieve, answer_evidence  # noqa: E402
from app.intelligence.assessments import grade  # noqa: E402
from app.config import settings  # noqa: E402
from app.intelligence.preparation import propose_roadmap, plan_view  # noqa: E402
from sqlalchemy import select  # noqa: E402

dataset = json.loads((ROOT / "benchmarks/synthetic-v1.json").read_text(encoding="utf-8"))
results = {
    "dataset": dataset["version"],
    "measured_at_utc": datetime.now(timezone.utc).isoformat(),
    "notice": dataset["notice"],
}
tp = fp = fn = 0
latencies = []
for case in dataset["resumes"]:
    started = time.perf_counter()
    observed = {c["skill"] for c in extract_resume(case["text"], use_model=False)["claims"]}
    latencies.append((time.perf_counter() - started) * 1000)
    expected = set(case["skills"])
    tp += len(observed & expected)
    fp += len(observed - expected)
    fn += len(expected - observed)
results["keyword_extraction"] = {
    "cases": len(dataset["resumes"]),
    "true_positive": tp,
    "false_positive": fp,
    "false_negative": fn,
    "precision": tp / (tp + fp) if tp + fp else 0,
    "recall": tp / (tp + fn) if tp + fn else 0,
    "mean_latency_ms": statistics.mean(latencies),
}
results["normalization"] = {
    "correct": sum(normalize(value) == expected for value, expected in dataset["normalization"]),
    "cases": len(dataset["normalization"]),
}
results["local_llm_comparison"] = {
    "status": "not_run",
    "reason": "Optional local model experiment must be run separately with installed model weights. No LLM result is inferred from fallback output.",
}
Base.metadata.create_all(engine)
with SessionLocal() as db:
    institution = Institution(slug="evaluation", name="Fictional Evaluation Institute")
    db.add(institution)
    db.flush()
    actor = User(
        institution_id=institution.id,
        roll_no="COORDINATOR",
        full_name="Fictional Coordinator",
        email="coordinator@example.com",
        role="institution_admin",
        active=True,
    )
    student = User(
        institution_id=institution.id,
        roll_no="SYN-EVAL",
        full_name="Fictional Student",
        email="student@example.com",
        role="student",
        active=True,
    )
    db.add_all([actor, student])
    db.flush()
    doc_ids = {}
    for item in dataset["documents"]:
        content = item["text"].encode()
        doc = InstitutionalDocument(
            institution_id=institution.id,
            title=item["title"],
            category="Synthetic benchmark",
            storage_key=get_storage().put(institution.id, content, ".txt"),
            filename=item["key"] + ".txt",
            mime_type="text/plain",
            size_bytes=len(content),
            uploaded_by=actor.id,
            status="approved",
            metadata_json={},
        )
        db.add(doc)
        db.flush()
        index_document(db, doc)
        doc_ids[item["key"]] = doc.id
    db.commit()
    precision = []
    recall = []
    citation_valid = 0
    citations = 0
    answered = 0
    unsupported = 0
    negative_queries = correct_abstentions = 0
    for case in dataset["queries"]:
        hits, method = retrieve(db, actor, case["question"], limit=1)
        found = {s["document_id"] for s in hits}
        expected = {doc_ids[key] for key in case["relevant"]}
        if not expected:
            negative_queries += 1
            correct_abstentions += not bool(found)
        if expected:
            precision.append(len(found & expected) / len(found) if found else 0)
            recall.append(len(found & expected) / len(expected))
        answer = answer_evidence(db, actor, case["question"])
        if answer["sources"]:
            answered += 1
            if any(s["quote"] not in answer["answer"] for s in answer["sources"]):
                unsupported += 1
        for source in answer["sources"]:
            citations += 1
            citation_valid += source["document_id"] in doc_ids.values() and source["quote"] in next(
                d["text"] for d in dataset["documents"] if doc_ids[d["key"]] == source["document_id"]
            )
    results["retrieval"] = {
        "method": method,
        "queries": len(dataset["queries"]),
        "positive_queries": len(precision),
        "negative_queries": negative_queries,
        "correct_abstentions": correct_abstentions,
        "precision_at_1": statistics.mean(precision),
        "recall_at_1": statistics.mean(recall),
        "source_citation_accuracy": citation_valid / citations if citations else None,
        "extractive_groundedness": 1 - unsupported / answered if answered else None,
        "unsupported_excerpt_frequency": unsupported / answered if answered else None,
        "definition": "Groundedness measures exact excerpt inclusion, not semantic correctness of an LLM or source authenticity.",
    }
    results["vector_hybrid_comparison"] = {
        "status": "not_run" if settings().embedding_mode != "sentence_transformers" else "configured_optional",
        "reason": "Requires cached Sentence Transformers weights and a running Qdrant service; keyword scores are not vector scores.",
    }
    successes = 0
    durations = []
    for case in dataset["resumes"][:3]:
        text_key = get_storage().put(institution.id, case["text"].encode(), ".txt")
        resume = Resume(
            institution_id=institution.id,
            user_id=student.id,
            filename="benchmark.txt",
            storage_key=text_key,
            text_key=text_key,
            mime_type="text/plain",
            size_bytes=len(case["text"]),
            version=len(durations) + 1,
        )
        db.add(resume)
        db.commit()
        started = time.perf_counter()
        run = dispatch(db, student, "resume", resume.id)
        durations.append((time.perf_counter() - started) * 1000)
        successes += run.status == "completed"
    results["agent_workflows"] = {
        "tasks": len(durations),
        "completed": successes,
        "completion_rate": successes / len(durations),
        "mean_latency_ms": statistics.mean(durations),
        "provider": "deterministic_fallback",
    }
    db.add(
        CareerGoal(
            institution_id=institution.id,
            user_id=student.id,
            payload={"role": "Python backend developer", "skills": ["Python", "SQL"], "hours_per_week": 6},
        )
    )
    db.flush()
    generic = propose_roadmap(db, student)
    generic.payload = {**generic.payload, "status": "active"}
    task = db.scalar(select(LearningTask).where(LearningTask.roadmap_id == generic.id))
    task.payload = {**task.payload, "status": "completed"}
    company = Company(institution_id=institution.id, name="Fictional .NET Evaluation Labs")
    db.add(company)
    db.flush()
    drive = RecruitmentDrive(
        institution_id=institution.id,
        company_id=company.id,
        position=".NET developer",
        description="Explicit synthetic requirements: C#, .NET and SQL Server.",
        employment_type="Full-time",
        location="Synthetic city",
        ctc="Illustrative",
        required_skills=["C#", ".NET", "SQL Server"],
        min_cgpa=6,
        max_backlogs=0,
        eligible_branches=[],
        graduation_year=2027,
        deadline=now() + timedelta(days=4),
        drive_date=now() + timedelta(days=5),
        status="published",
    )
    db.add(drive)
    db.flush()
    adapted = propose_roadmap(db, student, drive, "drive_published")
    generic_view = plan_view(db, generic)
    adapted_view = plan_view(db, adapted)
    required = set(drive.required_skills)

    def coverage(plan):
        return len({t["skill"] for t in plan["tasks"] if t["status"] != "completed"} & required) / len(required)

    results["roadmap_comparison"] = {
        "generic_target_overlap": coverage(generic_view),
        "drive_specific_target_overlap": coverage(adapted_view),
        "completed_tasks_before": generic_view["completed"],
        "completed_tasks_preserved": adapted_view["completed"],
        "new_effort_hours": sum(t["hours"] for t in adapted_view["tasks"] if t["status"] != "completed"),
        "hours_budget": adapted_view["hours_budget"],
        "definition": "Exact required-skill overlap of unfinished tasks in one synthetic scenario, not measured learning improvement or a placement outcome.",
    }
cases = [([0], [0], 100), ([1], [0], 0), ([0, 2], [0, 2], 100), ([0], [0, 2], 0), ([], [0], 0), ([0, 1], [0], 0)]
correct = 0
for answer, key, expected in cases:
    score = grade([{"id": "q", "kind": "multiple", "topic": "SQL", "correct": key, "points": 1}], {"q": answer})["score"]
    correct += score == expected
results["objective_grading"] = {"cases": len(cases), "correct": correct, "accuracy": correct / len(cases)}
test_results = ROOT / "data/backend-results.xml"
if test_results.exists():
    cases_by_name = {case.attrib["name"]: case for case in ET.parse(test_results).iter("testcase")}
    csv_case = cases_by_name.get("test_complete_1000_student_acceptance_flow")
    results["csv_import_reliability"] = {
        "status": "passed"
        if csv_case is not None and csv_case.find("failure") is None and csv_case.find("error") is None
        else "not_established",
        "rows_asserted": 1000,
        "source": "data/backend-results.xml: test_complete_1000_student_acceptance_flow",
        "end_to_end_case_seconds": float(csv_case.attrib["time"]) if csv_case is not None else None,
        "notice": "Includes activation, resume and drive steps; not isolated import throughput.",
    }
    security_names = [
        "test_complete_1000_student_acceptance_flow",
        "test_resume_graph_assessment_adaptation_and_boundaries",
        "test_evidence_sources_approval_expiry_and_tenant_filters",
        "test_vector_tenant_filter_and_revalidated_approval",
    ]
    results["tenant_isolation"] = {
        "named_cases": security_names,
        "passed": sum(
            name in cases_by_name and cases_by_name[name].find("failure") is None and cases_by_name[name].find("error") is None
            for name in security_names
        ),
        "source": "data/backend-results.xml",
        "notice": "Negative API/adapter cases; not an independent penetration test.",
    }
else:
    results["csv_import_reliability"] = {"status": "not_run", "reason": "Run pytest with --junitxml=data/backend-results.xml first."}
output = ROOT / "docs/evaluation-results.json"
output.write_text(json.dumps(results, indent=2), encoding="utf-8")
print(json.dumps(results, indent=2))
engine.dispose()
temporary.cleanup()
