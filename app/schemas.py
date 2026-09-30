"""Типы результатов проверки, общие для правил и HTTP API."""

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, Field


class RecordType(StrEnum):
    DAILY = "daily"
    WEEKLY = "weekly"


class CheckStatus(StrEnum):
    IN_PROGRESS = "check_in_progress"
    COMPLETE = "complete"
    INCOMPLETE = "incomplete"


class DocumentType(StrEnum):
    OBSERVATION_DIARY = "observation_diary"
    LESSON_REPORT = "lesson_report"
    PARENT_FEEDBACK = "parent_feedback"
    SPECIALIST_CONCLUSION = "specialist_conclusion"


class IssueLevel(StrEnum):
    WARNING = "warning"
    ERROR = "error"


class Issue(BaseModel):
    level: IssueLevel
    message: str


class Document(BaseModel):
    name: str
    detected_type: DocumentType | None
    size_kb: int = Field(ge=0)


class CheckOutcome(BaseModel):
    status: CheckStatus
    status_label: str
    reason: str
    issues: list[Issue]
    documents: list[Document]


class CheckResult(CheckOutcome):
    check_id: UUID
    record_type: RecordType
    extracted: dict = Field(default_factory=dict)
    checked_at: datetime | None


class CheckSummary(BaseModel):
    id: UUID
    created_at: datetime
    record_type: RecordType
    status: CheckStatus
    materials_count: int = Field(ge=0)
