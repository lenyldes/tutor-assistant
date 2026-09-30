"""Контрольные примеры 1–8 для независимой от БД проверки материалов."""

from unicodedata import normalize

import pytest

from app.checker import MAX_FILE_BYTES, FileMetadata, check_files, detect_type
from app.schemas import CheckStatus, DocumentType, IssueLevel, RecordType

DIARY = "дневник_наблюдений.xlsx"
REPORT = "отчёт_о_занятии.pdf"
FEEDBACK = "обратная_связь_родителя.docx"
CONCLUSION = "заключение_специалиста.png"


def files(*names: str, size: int = 1024) -> list[FileMetadata]:
    return [FileMetadata(name, size) for name in names]


def levels(result) -> list[IssueLevel]:
    return [issue.level for issue in result.issues]


def test_case_1_complete_daily() -> None:
    result = check_files(RecordType.DAILY, files(DIARY, REPORT, FEEDBACK))
    assert result.status == CheckStatus.COMPLETE
    assert result.reason == ""
    assert len(result.documents) == 3
    assert result.issues == []


def test_decomposed_unicode_names_keep_daily_complete() -> None:
    names = (normalize("NFD", DIARY), normalize("NFD", REPORT), FEEDBACK)
    result = check_files(RecordType.DAILY, files(*names))
    assert result.status == CheckStatus.COMPLETE
    assert result.issues == []
    assert [document.name for document in result.documents] == list(names)
    assert [document.detected_type for document in result.documents] == [
        DocumentType.OBSERVATION_DIARY,
        DocumentType.LESSON_REPORT,
        DocumentType.PARENT_FEEDBACK,
    ]


def test_case_2_complete_weekly() -> None:
    result = check_files(RecordType.WEEKLY, files(DIARY, REPORT, FEEDBACK, CONCLUSION))
    assert result.status == CheckStatus.COMPLETE
    assert len(result.documents) == 4
    assert result.issues == []


def test_case_3_missing_feedback() -> None:
    result = check_files(RecordType.DAILY, files(DIARY, REPORT))
    assert result.status == CheckStatus.INCOMPLETE
    assert len(result.documents) == 2
    assert levels(result) == [IssueLevel.ERROR]
    assert "обратная связь родителя" in result.reason


def test_case_4_unknown_extra_file_keeps_complete() -> None:
    result = check_files(RecordType.DAILY, files(DIARY, REPORT, FEEDBACK, "scan_0041.jpg"))
    assert result.status == CheckStatus.COMPLETE
    assert levels(result) == [IssueLevel.WARNING]
    assert result.documents[-1].detected_type is None


def test_case_5_invalid_format_does_not_count() -> None:
    result = check_files(
        RecordType.WEEKLY,
        files(DIARY, REPORT, FEEDBACK, "заключение_специалиста.exe"),
    )
    assert result.status == CheckStatus.INCOMPLETE
    assert levels(result) == [IssueLevel.WARNING, IssueLevel.ERROR]
    assert result.documents[-1].detected_type is None
    assert "заключение специалиста" in result.reason


def test_case_6_oversize_diary_does_not_count() -> None:
    entries = [FileMetadata(DIARY, MAX_FILE_BYTES + 1), *files(REPORT, FEEDBACK)]
    result = check_files(RecordType.DAILY, entries)
    assert result.status == CheckStatus.INCOMPLETE
    assert levels(result) == [IssueLevel.WARNING, IssueLevel.ERROR]
    assert result.documents[0].detected_type is None
    assert result.documents[0].size_kb == 20 * 1024 + 1


def test_case_7_exact_size_limit_is_valid() -> None:
    entries = [FileMetadata(DIARY, MAX_FILE_BYTES), *files(REPORT, FEEDBACK)]
    result = check_files(RecordType.DAILY, entries)
    assert result.status == CheckStatus.COMPLETE
    assert result.issues == []
    assert result.documents[0].size_kb == 20 * 1024


def test_case_8_duplicate_does_not_replace_feedback() -> None:
    result = check_files(
        RecordType.DAILY,
        files(DIARY, "ДНЕВНИК-НАБЛЮДЕНИЙ.pdf", REPORT),
    )
    assert result.status == CheckStatus.INCOMPLETE
    assert levels(result) == [IssueLevel.ERROR]
    assert [document.detected_type for document in result.documents[:2]] == [
        DocumentType.OBSERVATION_DIARY,
        DocumentType.OBSERVATION_DIARY,
    ]


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("ДНЕВНИК-НАБЛЮДЕНИЙ_15-03.XLSX", DocumentType.OBSERVATION_DIARY),
        ("отчёт_о_занятии.PDF", DocumentType.LESSON_REPORT),
        ("обратная связь родителя.docx", DocumentType.PARENT_FEEDBACK),
        ("заключение-специалиста.PNG", DocumentType.SPECIALIST_CONCLUSION),
    ],
)
def test_recognizes_case_and_separators(name: str, expected: DocumentType) -> None:
    assert detect_type(name) == expected
    result = check_files(RecordType.WEEKLY, files(name))
    assert result.documents[0].detected_type == expected


def test_invalid_extension_and_size_produce_two_warnings_in_order() -> None:
    result = check_files(
        RecordType.DAILY,
        [FileMetadata("дневник_наблюдений.exe", MAX_FILE_BYTES + 1)],
    )
    assert levels(result) == [
        IssueLevel.WARNING,
        IssueLevel.WARNING,
        IssueLevel.ERROR,
        IssueLevel.ERROR,
        IssueLevel.ERROR,
    ]
    assert "формат" in result.issues[0].message
    assert "размер" in result.issues[1].message
    assert result.documents[0].detected_type is None


def test_missing_categories_have_fixed_order() -> None:
    result = check_files(RecordType.WEEKLY, files("scan_0041.jpg"))
    assert levels(result) == [IssueLevel.WARNING] + [IssueLevel.ERROR] * 4
    for issue, phrase in zip(
        result.issues[1:],
        (
            "дневник наблюдений",
            "отчёт о занятии",
            "обратная связь родителя",
            "заключение специалиста",
        ),
        strict=True,
    ):
        assert phrase in issue.message
