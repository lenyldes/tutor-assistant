"""Точка входа FastAPI."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.checks import router as checks_router

app = FastAPI(title="Проверка материалов тьютора")
app.include_router(checks_router)

ROOT = Path(__file__).resolve().parent.parent
app.mount("/web", StaticFiles(directory=ROOT / "web"), name="web")
app.mount("/demo-files", StaticFiles(directory=ROOT / "demo_files"), name="demo-files")


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    """Отдаёт демонстрационную страницу из каталога проекта."""
    return FileResponse(ROOT / "web" / "index.html")
