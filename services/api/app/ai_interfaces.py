"""Phase 2 dependency boundaries: no AI packages are imported in Phase 1."""

from typing import Protocol, AsyncIterator
from pydantic import BaseModel


class TenantContext(BaseModel):
    institution_id: str
    actor_id: str


class ExtractedClaim(BaseModel):
    text: str
    source_document_id: str
    source_page: int | None = None
    confidence: float
    student_verified: bool = False


class LocalLLM(Protocol):
    def stream(self, prompt: str, *, context: TenantContext) -> AsyncIterator[str]: ...


class EmbeddingIndex(Protocol):
    async def search(self, query: str, *, context: TenantContext, limit: int = 5) -> list[ExtractedClaim]: ...


class WorkflowEngine(Protocol):
    async def run(self, workflow: str, document_id: str, *, context: TenantContext) -> str: ...
