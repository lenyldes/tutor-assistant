"""Подключение к PostgreSQL и сессия для обработчиков API."""

from collections.abc import Generator
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings


@lru_cache
def get_engine() -> Engine:
    """Создаёт одно подключение SQLAlchemy для приложения."""
    return create_engine(get_settings().database_url, pool_pre_ping=True)


@lru_cache
def get_session_factory() -> sessionmaker[Session]:
    """Возвращает фабрику сессий PostgreSQL."""
    return sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    """Передаёт сессию обработчику и закрывает её после запроса."""
    with get_session_factory()() as session:
        yield session
