from pydantic import BaseModel, Field
from .assessments import QuestionInput
from .question_catalog import QUESTIONS
from .providers import structured
from .taxonomy import normalize
from ..config import settings


class DraftBatch(BaseModel):
    questions: list[QuestionInput] = Field(min_length=1, max_length=5)


def draft_questions(topic, count):
    topic = normalize(topic)
    if not topic:
        raise ValueError("Choose a controlled taxonomy topic")
    if settings().ai_mode == "ollama":
        try:
            result = structured(
                "Create draft practice questions for human review. Include answer indexes and explanations. Do not claim they are approved. Use only the requested topic.",
                {"topic": topic, "count": count},
                DraftBatch,
            )
            questions = [q.model_dump() for q in result.questions[:count] if normalize(q.topic) == topic]
            if questions:
                return {"questions": questions, "provider": "ollama:" + settings().ollama_model, "approval_required": True}
        except Exception:
            pass
    questions = [QuestionInput.model_validate(q).model_dump() for q in QUESTIONS if q["topic"] == topic][:count]
    if not questions:
        raise ValueError("No curated fallback questions are available for this topic; create a faculty-authored question instead.")
    return {"questions": questions, "provider": "curated_synthetic_catalog", "approval_required": True}
