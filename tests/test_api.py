"""HTTP-контракт создания проверки, истории и промежуточного состояния."""

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Event
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.api import checks
from app.db import get_session_factory
from app.models import Check, CheckDocument

DIARY = "дневник_наблюдений.xlsx"
REPORT = "отчёт_о_занятии.pdf"
FEEDBACK = "обратная_связь_родителя.docx"
CONCLUSION = "заключение_специалиста.png"


def upload(client: TestClient, record_type: str, *names: str):
    return client.post(
        "/api/checks",
        data={"record_type": record_type},
        files=[("files", (name, b"sample", "application/octet-stream")) for name in names],
    )


def test_post_complete_daily_and_saved_result(client: TestClient) -> None:
    response = upload(client, "daily", DIARY, REPORT, FEEDBACK)
    assert response.status_code == 200
    result = response.json()
    assert result["record_type"] == "daily"
    assert result["status"] == "complete"
    assert result["status_label"] == "Запись полная — можно передавать в анализ"
    assert result["reason"] == ""
    assert result["issues"] == []
    assert result["extracted"] == {}
    assert result["checked_at"] is not None
    assert [document["detected_type"] for document in result["documents"]] == [
        "observation_diary",
        "lesson_report",
        "parent_feedback",
    ]
    assert [document["size_kb"] for document in result["documents"]] == [1, 1, 1]
    assert client.get(f"/api/checks/{result['check_id']}").json() == result


def test_post_incomplete_weekly_with_invalid_file(client: TestClient) -> None:
    response = upload(client, "weekly", DIARY, REPORT, FEEDBACK, "заключение_специалиста.exe")
    assert response.status_code == 200
    result = response.json()
    assert result["status"] == "incomplete"
    assert "заключение специалиста" in result["reason"]
    assert [issue["level"] for issue in result["issues"]] == ["warning", "error"]
    assert result["documents"][-1]["detected_type"] is None
    assert client.get(f"/api/checks/{result['check_id']}").json() == result


def test_post_incomplete_daily_missing_feedback(client: TestClient) -> None:
    result = upload(client, "daily", DIARY, REPORT).json()
    assert result["status"] == "incomplete"
    assert [issue["level"] for issue in result["issues"]] == ["error"]
    assert "обратная связь родителя" in result["reason"]


def test_post_warning_preserves_complete_and_every_file(client: TestClient) -> None:
    result = upload(client, "daily", DIARY, REPORT, FEEDBACK, "scan_0041.jpg").json()
    assert result["status"] == "complete"
    assert [issue["level"] for issue in result["issues"]] == ["warning"]
    assert result["documents"][-1]["detected_type"] is None
    assert result["extracted"] == {}
    assert client.get("/api/checks").json()[0]["materials_count"] == 4


def test_history_order_counts_and_details(client: TestClient) -> None:
    first = upload(client, "daily", DIARY, REPORT).json()
    second = upload(client, "weekly", DIARY, REPORT, FEEDBACK, CONCLUSION).json()
    factory = get_session_factory()
    with factory.begin() as db:
        earlier = db.get(Check, UUID(first["check_id"]))
        earlier.created_at = datetime.now(UTC) - timedelta(days=1)
    history = client.get("/api/checks")
    assert history.status_code == 200
    assert [row["id"] for row in history.json()] == [second["check_id"], first["check_id"]]
    assert [row["materials_count"] for row in history.json()] == [4, 2]
    assert [row["status"] for row in history.json()] == ["complete", "incomplete"]
    assert all(
        set(row) == {"id", "created_at", "record_type", "status", "materials_count"}
        for row in history.json()
    )
    assert client.get(f"/api/checks/{first['check_id']}").json() == first
    assert client.get(f"/api/checks/{second['check_id']}").json() == second


def test_unknown_id_returns_404(client: TestClient) -> None:
    assert client.get(f"/api/checks/{uuid4()}").status_code == 404


def test_invalid_requests_do_not_create_rows(client: TestClient) -> None:
    empty = client.post("/api/checks", data={"record_type": "daily"})
    invalid = upload(client, "monthly", DIARY)
    missing = client.post("/api/checks", files=[("files", (DIARY, b"x"))])
    assert empty.status_code == 400
    assert invalid.status_code == 422
    assert missing.status_code == 422
    assert client.get("/api/checks").json() == []


def test_parallel_read_sees_committed_intermediate_state(client: TestClient, monkeypatch) -> None:
    processing = Event()
    release = Event()
    real_check_files = checks.check_files

    def paused_check_files(record_type, metadata):
        processing.set()
        if not release.wait(timeout=10):
            raise TimeoutError("Обработка не была возобновлена")
        return real_check_files(record_type, metadata)

    monkeypatch.setattr(checks, "check_files", paused_check_files)
    with ThreadPoolExecutor(max_workers=1) as executor:
        pending = executor.submit(upload, client, "daily", DIARY, REPORT, FEEDBACK)
        try:
            assert processing.wait(timeout=10)
            history = client.get("/api/checks").json()
            assert len(history) == 1
            assert history[0]["status"] == "check_in_progress"
            assert history[0]["materials_count"] == 0
            detail = client.get(f"/api/checks/{history[0]['id']}").json()
            assert detail["status"] == "check_in_progress"
            assert detail["documents"] == []
            assert detail["issues"] == []
            assert detail["extracted"] == {}
            assert detail["checked_at"] is None
        finally:
            release.set()
        result = pending.result(timeout=10)
    assert result.status_code == 200
    assert client.get(f"/api/checks/{result.json()['check_id']}").json() == result.json()
    factory = get_session_factory()
    with factory() as db:
        assert db.scalar(select(CheckDocument.size_bytes)) == 6


def test_demo_page_styles_and_privacy_warning(client: TestClient) -> None:
    page = client.get("/")
    assert page.status_code == 200
    assert "text/html" in page.headers["content-type"]
    assert "Демо публичное." in page.text
    assert "Не загружайте персональные данные детей." in page.text
    assert 'data-scenario="unknown"' in page.text
    assert client.get("/web/style.css").status_code == 200
    assert client.get("/web/app.js").status_code == 200


def test_demo_files_are_served_without_changes(client: TestClient) -> None:
    folder = Path(__file__).resolve().parent.parent / "demo_files"
    names = (
        "дневник_наблюдений.xlsx",
        "отчёт_о_занятии.pdf",
        "обратная_связь_родителя.docx",
        "заключение_специалиста.png",
        "scan_0041.jpg",
        "заключение_специалиста.exe",
    )
    for name in names:
        response = client.get(f"/demo-files/{name}")
        assert response.status_code == 200
        assert response.content == (folder / name).read_bytes()
