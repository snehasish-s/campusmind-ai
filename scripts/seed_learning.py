"""Create a fictional question bank for demonstration; draft until an officer reviews it."""

import sys
from pathlib import Path
from sqlalchemy import select

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "services/api"))
from app.db import SessionLocal  # noqa: E402
from app.models import Institution, TestQuestion  # noqa: E402
from app.intelligence.assessments import QuestionInput  # noqa: E402

from app.intelligence.question_catalog import QUESTIONS  # noqa: E402


def seed(slug="demo"):
    with SessionLocal() as db:
        institution = db.scalar(select(Institution).where(Institution.slug == slug))
        if not institution:
            raise SystemExit("Create the synthetic institution with scripts/seed.py first.")
        existing = {q.payload.get("prompt") for q in db.scalars(select(TestQuestion).where(TestQuestion.institution_id == institution.id))}
        count = 0
        for raw in QUESTIONS:
            if raw["prompt"] not in existing:
                q = QuestionInput.model_validate(raw)
                db.add(
                    TestQuestion(
                        institution_id=institution.id,
                        payload={**q.model_dump(), "status": "draft", "provenance": "synthetic_demo_v1; officer review required"},
                    )
                )
                count += 1
        db.commit()
        print(f"Created {count} draft questions. Review and approve them in the assessment studio before publishing.")


if __name__ == "__main__":
    seed(sys.argv[1] if len(sys.argv) > 1 else "demo")
