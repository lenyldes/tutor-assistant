"""Создание проверок и чтение сохранённой истории."""

import logging
from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.checker import FileMetadata, check_files
from app.db import get_db
from app.models import Check, CheckDocument
from app.schemas import CheckResult, CheckSummary, Document, RecordType

router = APIRouter(prefix="/api/checks", tags=["checks"])
logger = logging.getLogger(__name__)
READ_CHUNK_BYTES = 1024 * 1024


def result_from_check(check: Check) -> CheckResult:
    """Собирает ответ исключительно из сохранённых полей."""
    return CheckResult(
        check_id=check.id,
        record_type=check.record_type,
        status=check.status,
        status_label=check.status_label,
        reason=check.reason,
        issues=check.issues,
        documents=[
            Document(
                name=document.name,
                detected_type=document.detected_type,
                size_kb=(document.size_bytes + 1023) // 1024,
            )
            for document in check.documents
        ],
        extracted=check.extracted,
        checked_at=check.checked_at,
    )


def read_metadata(files: list[UploadFile]) -> list[FileMetadata]:
    """Считает фактические байты потоком, не сохраняя содержимое."""
    metadata = []
    for file in files:
        size = 0
        while chunk := file.file.read(READ_CHUNK_BYTES):
            size += len(chunk)
        metadata.append(FileMetadata(name=file.filename or "", size_bytes=size))
    return metadata


@router.post("", response_model=CheckResult)
def create_check(
    record_type: Annotated[RecordType, Form()],
    db: Annotated[Session, Depends(get_db)],
    files: Annotated[list[UploadFile] | None, File()] = None,
) -> CheckResult:
    if not files:
        raise HTTPException(status_code=400, detail="Добавьте хотя бы один файл")

    check = Check(record_type=record_type.value)
    db.add(check)
    db.commit()

    try:
        metadata = read_metadata(files)
        outcome = check_files(record_type, metadata)
        check.status = outcome.status.value
        check.status_label = outcome.status_label
        check.reason = outcome.reason
        check.issues = [issue.model_dump(mode="json") for issue in outcome.issues]
        check.checked_at = datetime.now(UTC)
        check.documents = [
            CheckDocument(
                position=position,
                name=file.name,
                detected_type=document.detected_type.value if document.detected_type else None,
                size_bytes=file.size_bytes,
            )
            for position, (file, document) in enumerate(
                zip(metadata, outcome.documents, strict=True)
            )
        ]
        db.commit()
        db.refresh(check)
        return result_from_check(check)
    except Exception:
        db.rollback()
        logger.exception("Не удалось завершить проверку %s", check.id)
        raise HTTPException(status_code=500, detail="Не удалось завершить проверку") from None
    finally:
        for file in files:
            file.file.close()


@router.get("", response_model=list[CheckSummary])
def list_checks(db: Annotated[Session, Depends(get_db)]) -> list[CheckSummary]:
    count = func.count(CheckDocument.id).label("materials_count")
    rows = db.execute(
        select(Check, count)
        .outerjoin(CheckDocument)
        .group_by(Check.id)
        .order_by(Check.created_at.desc(), Check.id.desc())
    ).all()
    return [
        CheckSummary(
            id=check.id,
            created_at=check.created_at,
            record_type=check.record_type,
            status=check.status,
            materials_count=materials_count,
        )
        for check, materials_count in rows
    ]


@router.get("/{check_id}", response_model=CheckResult)
def get_check(check_id: UUID, db: Annotated[Session, Depends(get_db)]) -> CheckResult:
    check = db.scalar(
        select(Check).options(selectinload(Check.documents)).where(Check.id == check_id)
    )
    if check is None:
        raise HTTPException(status_code=404, detail="Проверка не найдена")
    return result_from_check(check)
