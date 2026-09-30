"""Изолированная PostgreSQL для проверок HTTP API."""

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.db import get_session_factory
from app.main import app
from app.models import Check


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    factory = get_session_factory()
    with factory.begin() as db:
        db.execute(delete(Check))
    with TestClient(app) as test_client:
        yield test_client
    with factory.begin() as db:
        db.execute(delete(Check))
