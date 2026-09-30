"""Точка входа FastAPI."""

from fastapi import FastAPI

from app.api.checks import router as checks_router

app = FastAPI(title="Проверка материалов тьютора")
app.include_router(checks_router)
