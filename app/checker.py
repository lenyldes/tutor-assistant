"""Чистая проверка имён, размеров и комплектности загруженных материалов."""

import re
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import PurePath
from unicodedata import normalize

from app.schemas import (
    CheckOutcome,
    CheckStatus,
    Document,
    DocumentType,
    Issue,
    IssueLevel,
    RecordType,
)

MAX_FILE_BYTES = 20 * 1024 * 1024
ALLOWED_EXTENSIONS = frozenset({".pdf", ".docx", ".xlsx", ".jpg", ".png"})

TYPE_PHRASES = {
    DocumentType.OBSERVATION_DIARY: "дневник наблюдений",
    DocumentType.LESSON_REPORT: "отчёт о занятии",
    DocumentType.PARENT_FEEDBACK: "обратная связь родителя",
    DocumentType.SPECIALIST_CONCLUSION: "заключение специалиста",
}


@dataclass(frozen=True)
class FileMetadata:
    name: str
    size_bytes: int


def detect_type(name: str) -> DocumentType | None:
    """Находит категорию по последовательности слов в имени без расширения."""
    words = re.split(r"[\s_-]+", normalize("NFC", PurePath(name).stem.casefold()))
    for category, phrase in TYPE_PHRASES.items():
        phrase_words = phrase.split()
        width = len(phrase_words)
        if any(
            words[index : index + width] == phrase_words for index in range(len(words) - width + 1)
        ):
            return category
    return None


def check_files(record_type: RecordType, files: Iterable[FileMetadata]) -> CheckOutcome:
    """Проверяет метаданные файлов без обращения к содержимому и хранилищу."""
    issues: list[Issue] = []
    documents: list[Document] = []
    present: set[DocumentType] = set()

    for file in files:
        if file.size_bytes < 0:
            raise ValueError("Размер файла не может быть отрицательным")

        extension = PurePath(file.name).suffix.casefold()
        valid_extension = extension in ALLOWED_EXTENSIONS
        valid_size = file.size_bytes <= MAX_FILE_BYTES

        if not valid_extension:
            issues.append(
                Issue(level=IssueLevel.WARNING, message=f"Недопустимый формат файла: «{file.name}»")
            )
        if not valid_size:
            issues.append(
                Issue(level=IssueLevel.WARNING, message=f"Превышен размер 20 МБ: «{file.name}»")
            )

        category = detect_type(file.name) if valid_extension and valid_size else None
        if valid_extension and valid_size and category is None:
            issues.append(
                Issue(
                    level=IssueLevel.WARNING,
                    message=f"Не удалось определить тип материала: «{file.name}»",
                )
            )
        if category is not None:
            present.add(category)

        documents.append(
            Document(
                name=file.name,
                detected_type=category,
                size_kb=(file.size_bytes + 1023) // 1024,
            )
        )

    required = list(TYPE_PHRASES)
    if record_type == RecordType.DAILY:
        required.remove(DocumentType.SPECIALIST_CONCLUSION)
    elif record_type != RecordType.WEEKLY:
        raise ValueError(f"Неизвестный тип записи: {record_type}")

    missing = [TYPE_PHRASES[category] for category in required if category not in present]
    for phrase in missing:
        issues.append(
            Issue(level=IssueLevel.ERROR, message=f"Отсутствует обязательный материал: {phrase}")
        )

    if missing:
        return CheckOutcome(
            status=CheckStatus.INCOMPLETE,
            status_label="Запись неполная — нельзя передавать в анализ",
            reason="Отсутствуют обязательные материалы: " + ", ".join(missing),
            issues=issues,
            documents=documents,
        )
    return CheckOutcome(
        status=CheckStatus.COMPLETE,
        status_label="Запись полная — можно передавать в анализ",
        reason="",
        issues=issues,
        documents=documents,
    )
