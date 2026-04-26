"""Shared test fixtures — runs against real PostgreSQL, never SQLite.

Start the dev stack first:
    docker compose -f deploy/docker-compose.dev.yml up -d postgres redis
"""

import os
from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db import Base, get_db
from app.main import app

TEST_DATABASE_URL = (
    os.environ.get("TEST_DATABASE_URL")
    or os.environ.get("DATABASE_URL")
    or "postgresql+psycopg://postgres:postgres@localhost:5432/eventgame_test"
)

_engine = create_engine(TEST_DATABASE_URL)


@pytest.fixture(scope="session")
def create_tables() -> Generator[None, None, None]:
    """Create schema once per session; drop everything after."""
    Base.metadata.create_all(_engine)
    yield
    Base.metadata.drop_all(_engine)


@pytest.fixture
def db_session(create_tables: None) -> Generator[Session, None, None]:
    """Transactional session — every test rolls back, leaving the DB clean."""
    conn = _engine.connect()
    trans = conn.begin()
    session = Session(conn, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        trans.rollback()
        conn.close()


@pytest.fixture
def client(db_session: Session) -> Generator[TestClient, None, None]:
    """TestClient with the DB dependency wired to the test session."""

    def _override() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db] = _override
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def auth_client(db_session: Session) -> Generator[TestClient, None, None]:
    """TestClient with an authenticated user.

    Phase 1: also override get_current_user with a seeded test user and
    inject a valid JWT cookie so auth middleware passes.
    """

    def _override() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db] = _override
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def mock_ai() -> Generator[MagicMock, None, None]:
    """Patch all AI provider calls — prevents real LLM requests during tests."""
    with patch("app.services.providers.get_provider") as mock:
        mock.return_value.complete = MagicMock(return_value="mocked AI response")
        yield mock
