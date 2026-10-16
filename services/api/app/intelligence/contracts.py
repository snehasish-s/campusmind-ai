from typing import Literal
from pydantic import BaseModel, Field, ConfigDict


class EvidenceClaim(BaseModel):
    model_config = ConfigDict(extra="forbid")
    skill: str = Field(max_length=80)
    quote: str = Field(min_length=2, max_length=600)
    confidence: float = Field(ge=0, le=1)
    ambiguous: bool = False
    evidence_type: Literal["resume_claim"] = "resume_claim"
    explanation: str = Field(max_length=500)


class ResumeResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    claims: list[EvidenceClaim] = Field(default_factory=list, max_length=30)
    projects: list[str] = Field(default_factory=list, max_length=20)
    internships: list[str] = Field(default_factory=list, max_length=20)
    certifications: list[str] = Field(default_factory=list, max_length=20)
    limitations: list[str] = Field(default_factory=list, max_length=10)


class JobRequirement(BaseModel):
    model_config = ConfigDict(extra="forbid")
    skill: str
    priority: Literal["required", "preferred", "unclear"]
    quote: str = Field(max_length=1000)


class RecruitmentResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    skills: list[JobRequirement] = Field(default_factory=list, max_length=40)
    responsibilities: list[str] = Field(default_factory=list, max_length=20)
    stated_conditions: list[str] = Field(default_factory=list, max_length=20)
    ambiguities: list[str] = Field(default_factory=list, max_length=20)


class AdvisoryAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid")
    answer: str = Field(min_length=1, max_length=6000)
    source_ids: list[str] = Field(default_factory=list, max_length=10)
    insufficient_evidence: bool = False
