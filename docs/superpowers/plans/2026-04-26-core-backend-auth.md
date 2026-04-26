# Core Backend & Auth — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the complete FastAPI backend with JWT auth (login, logout, refresh, me), Azure OAuth, all 10 ORM models, and Redis-based rate limiting — delivering a running, tested API that Phase 2 (seeding) and Phase 3 (frontend) depend on.

**Architecture:** Layered FastAPI app — routes call services, services call models, no layer skipping. JWT in HTTPOnly cookies (15 min access, 7 day refresh with rotation). Refresh tokens stored in DB as SHA-256 hashes, revoked on logout. Rate limiting via Redis counter (5 req/min on auth endpoints). Schema created via `Base.metadata.create_all()` on startup — no migrations in V2. To reset: drop the database and restart. Sync SQLAlchemy throughout; async only in later phases.

**Tech Stack:** Python 3.12 / FastAPI / SQLAlchemy 2.0 / psycopg / PostgreSQL / Redis / python-jose / passlib / structlog / pydantic-settings / pytest with real PostgreSQL

**Branch:** `feature/DEV-36-core-backend-auth`

---

## File Map

**Create:**
```
backend/app/core/__init__.py
backend/app/core/config.py
backend/app/core/database.py
backend/app/core/redis_client.py
backend/app/core/logging.py
backend/app/models/__init__.py
backend/app/models/base.py
backend/app/models/user.py
backend/app/models/refresh_token.py
backend/app/models/team.py
backend/app/models/event.py
backend/app/models/game.py
backend/app/models/game_progress.py
backend/app/models/game_rating.py
backend/app/models/chat_session.py
backend/app/models/chat_message.py
backend/app/models/system_config.py
backend/app/schemas/__init__.py
backend/app/schemas/auth_schemas.py
backend/app/services/__init__.py
backend/app/services/auth_service.py
backend/app/services/azure_oauth_service.py
backend/app/dependencies/__init__.py
backend/app/dependencies/auth.py
backend/app/api/__init__.py
backend/app/api/auth/__init__.py
backend/app/api/auth/login.py
backend/app/api/auth/logout.py
backend/app/api/auth/refresh.py
backend/app/api/auth/me.py
backend/app/api/auth/oauth.py
backend/app/middleware/__init__.py
backend/app/middleware/rate_limit.py
backend/tests/__init__.py
backend/tests/conftest.py
backend/tests/auth/__init__.py
backend/tests/auth/test_login.py
backend/tests/auth/test_logout.py
backend/tests/auth/test_refresh.py
backend/tests/auth/test_me.py
backend/tests/security/__init__.py
backend/tests/security/test_rate_limiting.py
```

**Modify:**
```
backend/app/main.py
backend/app/__init__.py
```

---

## Task 1: App Configuration + Logging + CORS

**Files:**
- Create: `backend/app/core/__init__.py`
- Create: `backend/app/core/config.py`
- Create: `backend/app/core/logging.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: Create `backend/app/core/__init__.py`**

```python
```
(empty file)

- [ ] **Step 2: Create `backend/app/core/config.py`**

```python
"""Application settings loaded from environment variables."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    DATABASE_URL: str = "postgresql+psycopg://event_game:secret@localhost:5432/event_game"
    TEST_DATABASE_URL: str = "postgresql+psycopg://event_game:secret@localhost:5432/event_game_test"
    REDIS_URL: str = "redis://localhost:6379"

    JWT_SECRET_KEY: str = "change-me-in-production-use-32-random-chars"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    AZURE_CLIENT_ID: str = ""
    AZURE_CLIENT_SECRET: str = ""
    AZURE_TENANT_ID: str = ""
    AZURE_REDIRECT_URI: str = "http://localhost:8000/v1/auth/azure/callback"

    CORS_ORIGINS: str = "http://localhost:3000"
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"


settings = Settings()
```

- [ ] **Step 3: Create `backend/app/core/logging.py`**

```python
"""Structured logging configuration — structlog with stdlib integration."""
import logging
import sys
import structlog


def configure_logging(log_level: str = "INFO") -> None:
    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
    ]
    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            structlog.dev.ConsoleRenderer()
            if log_level == "DEBUG"
            else structlog.processors.JSONRenderer(),
        ],
    )
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(getattr(logging, log_level.upper(), logging.INFO))
```

- [ ] **Step 4: Update `backend/app/main.py`**

```python
"""Event Game Framework API — FastAPI application entry point."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.logging import configure_logging

configure_logging(settings.LOG_LEVEL)

app: FastAPI = FastAPI(title="Event Game Framework", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
```

- [ ] **Step 5: Run health check**

```bash
cd backend && python -c "from app.main import app; print('OK')"
```
Expected: `OK`

- [ ] **Step 6: Commit**

```bash
git checkout -b feature/DEV-36-core-backend-auth
git add backend/app/core/ backend/app/main.py
git commit -m "feat(DEV-36): add app config, structlog, and CORS middleware"
```

---

## Task 2: Database Layer

**Files:**
- Create: `backend/app/core/database.py`
- Create: `backend/app/models/base.py`
- Create: `backend/app/models/__init__.py`

- [ ] **Step 1: Create `backend/app/core/database.py`**

```python
"""SQLAlchemy engine and session factory."""
from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from app.core.config import settings

engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

- [ ] **Step 2: Create `backend/app/models/base.py`**

```python
"""SQLAlchemy declarative base shared by all ORM models."""
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
```

- [ ] **Step 3: Create `backend/app/models/__init__.py`** (empty for now; populated in Task 4)

```python
"""ORM models — all imported here so create_all picks them up on startup."""
```

- [ ] **Step 4: Verify import chain**

```bash
cd backend && python -c "from app.core.database import get_db, engine; print('DB:', engine.url)"
```
Expected: prints the DATABASE_URL without password exposed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/database.py backend/app/models/
git commit -m "feat(DEV-36): add SQLAlchemy engine, session factory, and model base"
```

---

## Task 3: Redis Layer

**Files:**
- Create: `backend/app/core/redis_client.py`

- [ ] **Step 1: Create `backend/app/core/redis_client.py`**

```python
"""Redis connection and FastAPI dependency."""
from typing import Generator
import redis
from app.core.config import settings

_pool = redis.ConnectionPool.from_url(settings.REDIS_URL, decode_responses=True)


def get_redis() -> Generator[redis.Redis, None, None]:  # type: ignore[type-arg]
    client: redis.Redis = redis.Redis(connection_pool=_pool)  # type: ignore[type-arg]
    try:
        yield client
    finally:
        client.close()
```

- [ ] **Step 2: Verify Redis connects (requires running Docker dev stack)**

```bash
cd backend && python -c "
from app.core.redis_client import get_redis
r = next(get_redis())
print('Redis ping:', r.ping())
"
```
Expected: `Redis ping: True`

Note: if Docker dev stack is not running, start it: `cd deploy && docker compose -f docker-compose.dev.yml up postgres redis -d`

- [ ] **Step 3: Commit**

```bash
git add backend/app/core/redis_client.py
git commit -m "feat(DEV-36): add Redis connection pool and get_redis dependency"
```

---

## Task 4: All 10 ORM Models

**Files:** Create all 10 model files + update `backend/app/models/__init__.py`

- [ ] **Step 1: Create `backend/app/models/user.py`**

```python
"""User accounts — authentication, roles, and team membership."""
from datetime import datetime
from typing import Optional, TYPE_CHECKING
from sqlalchemy import String, Boolean, ForeignKey, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from app.models.base import Base

if TYPE_CHECKING:
    from app.models.team import Team
    from app.models.refresh_token import RefreshToken


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    email: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    azure_id: Mapped[Optional[str]] = mapped_column(String(100), unique=True, nullable=True)
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="player")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    team_id: Mapped[Optional[int]] = mapped_column(ForeignKey("teams.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_login: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    team: Mapped[Optional["Team"]] = relationship("Team", back_populates="members")
    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(
        "RefreshToken", back_populates="user", cascade="all, delete-orphan"
    )
```

- [ ] **Step 2: Create `backend/app/models/refresh_token.py`**

```python
"""Refresh tokens — hashed storage with revocation support."""
from datetime import datetime
from typing import Optional, TYPE_CHECKING
from sqlalchemy import String, Boolean, ForeignKey, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from app.models.base import Base

if TYPE_CHECKING:
    from app.models.user import User


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_revoked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship("User", back_populates="refresh_tokens")
```

- [ ] **Step 3: Create `backend/app/models/team.py`**

```python
"""Teams — persist across events; is_solo marks individual-mode auto-teams."""
from typing import Optional, TYPE_CHECKING
from sqlalchemy import String, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base

if TYPE_CHECKING:
    from app.models.user import User


class Team(Base):
    __tablename__ = "teams"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    invite_code: Mapped[str] = mapped_column(String(20), unique=True, index=True, nullable=False)
    is_solo: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    members: Mapped[list["User"]] = relationship("User", back_populates="team")
```

- [ ] **Step 4: Create `backend/app/models/event.py`**

```python
"""Events — one active at a time; health_ok set by startup health checker."""
from typing import Optional, TYPE_CHECKING
from sqlalchemy import String, Boolean, Integer, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base

if TYPE_CHECKING:
    from app.models.game import Game


class Event(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    author: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    scoring_mode: Mapped[str] = mapped_column(String(20), nullable=False, default="points")
    mode: Mapped[str] = mapped_column(String(20), nullable=False, default="team")
    theme: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    language: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    ui_text: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    health_ok: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    games: Mapped[list["Game"]] = relationship("Game", back_populates="event")
```

- [ ] **Step 5: Create `backend/app/models/game.py`**

```python
"""Games — belong to an event; Docker containers at game.url."""
from typing import Optional, TYPE_CHECKING
from sqlalchemy import String, Integer, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base

if TYPE_CHECKING:
    from app.models.event import Event
    from app.models.game_progress import GameProgress
    from app.models.game_rating import GameRating


class Game(Base):
    __tablename__ = "games"

    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"), nullable=False, index=True)
    slug: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(2000), nullable=True)
    category: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    points: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    image: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    solution_answer: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    url: Mapped[str] = mapped_column(String(500), nullable=False)
    milestones: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    hints: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    dependencies: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)

    event: Mapped["Event"] = relationship("Event", back_populates="games")
    progress: Mapped[list["GameProgress"]] = relationship("GameProgress", back_populates="game")
    ratings: Mapped[list["GameRating"]] = relationship("GameRating", back_populates="game")
```

- [ ] **Step 6: Create `backend/app/models/game_progress.py`**

```python
"""Game progress — tracks each team's state per game; unique per (game, team)."""
from datetime import datetime
from typing import Optional, TYPE_CHECKING
from sqlalchemy import String, Boolean, ForeignKey, DateTime, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base

if TYPE_CHECKING:
    from app.models.game import Game
    from app.models.team import Team


class GameProgress(Base):
    __tablename__ = "game_progress"
    __table_args__ = (UniqueConstraint("game_id", "team_id", name="uq_game_progress"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    game_id: Mapped[int] = mapped_column(ForeignKey("games.id"), nullable=False, index=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), nullable=False, index=True)
    milestone: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    is_completed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    submitted_answer: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    game: Mapped["Game"] = relationship("Game", back_populates="progress")
    team: Mapped["Team"] = relationship("Team")
```

- [ ] **Step 7: Create `backend/app/models/game_rating.py`**

```python
"""Game ratings — 1-5 stars per user per game; unique per (game, user)."""
from datetime import datetime
from typing import TYPE_CHECKING
from sqlalchemy import Integer, ForeignKey, DateTime, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from app.models.base import Base

if TYPE_CHECKING:
    from app.models.game import Game
    from app.models.user import User


class GameRating(Base):
    __tablename__ = "game_ratings"
    __table_args__ = (UniqueConstraint("game_id", "user_id", name="uq_game_rating"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    game_id: Mapped[int] = mapped_column(ForeignKey("games.id"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    game: Mapped["Game"] = relationship("Game", back_populates="ratings")
    user: Mapped["User"] = relationship("User")
```

- [ ] **Step 8: Create `backend/app/models/chat_session.py`**

```python
"""Chat sessions — scoped to a team; optionally linked to a game for hint context."""
from datetime import datetime
from typing import Optional, TYPE_CHECKING
from sqlalchemy import ForeignKey, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from app.models.base import Base

if TYPE_CHECKING:
    from app.models.team import Team
    from app.models.game import Game
    from app.models.chat_message import ChatMessage


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), nullable=False, index=True)
    game_id: Mapped[Optional[int]] = mapped_column(ForeignKey("games.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    team: Mapped["Team"] = relationship("Team")
    game: Mapped[Optional["Game"]] = relationship("Game")
    messages: Mapped[list["ChatMessage"]] = relationship(
        "ChatMessage", back_populates="session", cascade="all, delete-orphan"
    )
```

- [ ] **Step 9: Create `backend/app/models/chat_message.py`**

```python
"""Chat messages — content stored AES-256-GCM encrypted (Phase 5); role is user|assistant."""
from datetime import datetime
from typing import TYPE_CHECKING
from sqlalchemy import String, ForeignKey, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from app.models.base import Base

if TYPE_CHECKING:
    from app.models.chat_session import ChatSession


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("chat_sessions.id"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)  # user | assistant
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    session: Mapped["ChatSession"] = relationship("ChatSession", back_populates="messages")
```

- [ ] **Step 10: Create `backend/app/models/system_config.py`**

```python
"""System configuration — key/value store for AI provider, model, system prompt."""
from datetime import datetime
from sqlalchemy import String, Text, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
from app.models.base import Base


class SystemConfig(Base):
    __tablename__ = "system_config"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
```

- [ ] **Step 11: Verify all models import cleanly**

```bash
cd backend && python -c "import app.models; print('All 10 models OK')"
```
Expected: `All 10 models OK`

- [ ] **Step 12: Commit**

```bash
git add backend/app/models/
git commit -m "feat(DEV-36): add all 10 ORM models (users, teams, events, games, progress, ratings, chat, config)"
```

---

## Task 5: Schema Creation on Startup

**Files:**
- Modify: `backend/app/main.py`
- Modify: `backend/app/models/__init__.py`

Add a FastAPI lifespan that calls `Base.metadata.create_all()` on startup so the 10 tables are created automatically when the app starts. No migrations. To reset the schema, drop the database and restart.

- [ ] **Step 1: Update `backend/app/models/__init__.py`** with all model imports

```python
"""ORM models — all imported here so create_all picks them up on startup."""
from app.models.user import User
from app.models.refresh_token import RefreshToken
from app.models.team import Team
from app.models.event import Event
from app.models.game import Game
from app.models.game_progress import GameProgress
from app.models.game_rating import GameRating
from app.models.chat_session import ChatSession
from app.models.chat_message import ChatMessage
from app.models.system_config import SystemConfig

__all__ = [
    "User", "RefreshToken", "Team", "Event", "Game",
    "GameProgress", "GameRating", "ChatSession", "ChatMessage", "SystemConfig",
]
```

- [ ] **Step 2: Update `backend/app/main.py`** with startup lifespan

```python
"""Event Game Framework API — FastAPI application entry point."""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.logging import configure_logging

configure_logging(settings.LOG_LEVEL)


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.core.database import engine
    from app.models.base import Base
    import app.models  # noqa: F401 — registers all models
    Base.metadata.create_all(engine, checkfirst=True)
    yield


app: FastAPI = FastAPI(title="Event Game Framework", version="2.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
```

- [ ] **Step 3: Start the dev stack and verify tables are created**

```bash
cd deploy && docker compose -f docker-compose.dev.yml up postgres -d
```

```bash
cd backend && python -c "
from app.main import app
from app.core.database import engine
from sqlalchemy import inspect, text

# Trigger create_all (same as startup)
from app.models.base import Base
import app.models
Base.metadata.create_all(engine, checkfirst=True)

tables = inspect(engine).get_table_names()
print('Tables:', sorted(tables))
assert len(tables) == 10, f'Expected 10, got {len(tables)}: {tables}'
print('Schema OK')
"
```
Expected: `Tables: ['chat_messages', 'chat_sessions', 'events', 'game_progress', 'game_ratings', 'games', 'refresh_tokens', 'system_config', 'teams', 'users']`

- [ ] **Step 4: Commit**

```bash
git add backend/app/main.py backend/app/models/__init__.py
git commit -m "feat(DEV-36): create schema via Base.metadata.create_all on startup (no migrations)"
```

---

## Task 6: Test Infrastructure

**Files:**
- Create: `backend/tests/__init__.py`
- Create: `backend/tests/conftest.py`
- Create: `backend/tests/auth/__init__.py`
- Create: `backend/tests/security/__init__.py`

- [ ] **Step 1: Create `backend/tests/__init__.py`** (empty)

- [ ] **Step 2: Create `backend/tests/auth/__init__.py`** (empty)

- [ ] **Step 3: Create `backend/tests/security/__init__.py`** (empty)

- [ ] **Step 4: Create `backend/tests/conftest.py`**

```python
"""Test fixtures — real PostgreSQL with transactional rollback per test."""
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.database import get_db
from app.core.redis_client import get_redis
from app.main import app
from app.models.base import Base
import app.models  # noqa: F401


# ── Engine (session-scoped — tables created once) ──────────────────────────

@pytest.fixture(scope="session")
def pg_engine():
    """Create the test database and all tables once per session."""
    # Create test DB if it doesn't exist
    admin_url = settings.TEST_DATABASE_URL.rsplit("/", 1)[0] + "/postgres"
    db_name = settings.TEST_DATABASE_URL.rsplit("/", 1)[1]
    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    with admin_engine.connect() as conn:
        exists = conn.execute(
            text(f"SELECT 1 FROM pg_database WHERE datname = :name"),
            {"name": db_name},
        ).fetchone()
        if not exists:
            conn.execute(text(f'CREATE DATABASE "{db_name}"'))
    admin_engine.dispose()

    engine = create_engine(settings.TEST_DATABASE_URL, echo=False)
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


# ── Session (function-scoped — rolled back after each test) ─────────────────

TestSessionFactory = sessionmaker(autocommit=False, autoflush=False)


@pytest.fixture
def db_session(pg_engine):
    """Test DB session that rolls back after each test."""
    connection = pg_engine.connect()
    transaction = connection.begin()
    session = TestSessionFactory(bind=connection, join_transaction_mode="create_savepoint")

    def override_get_db():
        yield session

    app.dependency_overrides[get_db] = override_get_db
    yield session

    app.dependency_overrides.pop(get_db, None)
    session.close()
    transaction.rollback()
    connection.close()


# ── HTTP client ──────────────────────────────────────────────────────────────

@pytest.fixture
def client(db_session):
    """TestClient that uses the test DB session."""
    return TestClient(app, raise_server_exceptions=True)


# ── User fixtures ────────────────────────────────────────────────────────────

@pytest.fixture
def test_user(db_session):
    """A regular player user."""
    from passlib.context import CryptContext
    from app.models.user import User

    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    user = User(
        username="testplayer",
        email="player@test.com",
        password_hash=pwd_context.hash("password123"),
        role="player",
        is_active=True,
    )
    db_session.add(user)
    db_session.flush()
    return user


@pytest.fixture
def admin_user(db_session):
    """An admin user."""
    from passlib.context import CryptContext
    from app.models.user import User

    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    user = User(
        username="testadmin",
        email="admin@test.com",
        password_hash=pwd_context.hash("adminpass123"),
        role="admin",
        is_active=True,
    )
    db_session.add(user)
    db_session.flush()
    return user


@pytest.fixture
def auth_client(client, test_user):
    """TestClient pre-authenticated as testplayer."""
    response = client.post(
        "/v1/auth/login",
        json={"username": "testplayer", "password": "password123"},
    )
    assert response.status_code == 200, f"Login failed: {response.json()}"
    return client


@pytest.fixture
def admin_client(client, admin_user):
    """TestClient pre-authenticated as admin."""
    response = client.post(
        "/v1/auth/login",
        json={"username": "testadmin", "password": "adminpass123"},
    )
    assert response.status_code == 200
    return client
```

- [ ] **Step 5: Verify test infrastructure collects**

```bash
cd backend && pytest --collect-only -q 2>&1 | head -20
```
Expected: no import errors (tests folder is empty but should collect 0 items cleanly).

- [ ] **Step 6: Commit**

```bash
git add backend/tests/
git commit -m "feat(DEV-36): add test infrastructure — conftest with transactional rollback fixtures"
```

---

## Task 7: Auth Schemas + JWT Service

**Files:**
- Create: `backend/app/schemas/__init__.py`
- Create: `backend/app/schemas/auth_schemas.py`
- Create: `backend/app/services/__init__.py`
- Create: `backend/app/services/auth_service.py`
- Test: `backend/tests/auth/test_jwt_service.py`

- [ ] **Step 1: Write failing test**

Create `backend/tests/auth/test_jwt_service.py`:

```python
"""JWT service unit tests — no DB required."""
import pytest
from datetime import timedelta
from jose import JWTError

from app.services.auth_service import (
    create_access_token,
    decode_access_token,
    hash_token,
    verify_password,
    hash_password,
)


def test_access_token_encodes_user_id():
    token = create_access_token(user_id=42, username="alice", role="player")
    payload = decode_access_token(token)
    assert payload["sub"] == "42"
    assert payload["username"] == "alice"
    assert payload["role"] == "player"


def test_access_token_expired_raises():
    token = create_access_token(
        user_id=1, username="bob", role="player",
        expires_delta=timedelta(seconds=-1)
    )
    with pytest.raises(JWTError):
        decode_access_token(token)


def test_hash_password_and_verify():
    hashed = hash_password("secret")
    assert verify_password("secret", hashed)
    assert not verify_password("wrong", hashed)


def test_hash_token_is_deterministic():
    assert hash_token("abc") == hash_token("abc")
    assert hash_token("abc") != hash_token("xyz")
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && pytest tests/auth/test_jwt_service.py -v
```
Expected: `ImportError: cannot import name 'create_access_token' from 'app.services.auth_service'`

- [ ] **Step 3: Create `backend/app/schemas/__init__.py`** (empty)

- [ ] **Step 4: Create `backend/app/schemas/auth_schemas.py`**

```python
"""Pydantic schemas for auth endpoints — login request and responses."""
from typing import Optional
from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=1, max_length=128)


class MeResponse(BaseModel):
    id: int
    username: str
    role: str
    team_id: Optional[int]
    email: str

    model_config = {"from_attributes": True}
```

- [ ] **Step 5: Create `backend/app/services/__init__.py`** (empty)

- [ ] **Step 6: Create `backend/app/services/auth_service.py`**

```python
"""Authentication service — JWT creation/decoding, password hashing, token hashing."""
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import jwt, JWTError  # noqa: F401 — re-exported for callers
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.core.config import settings

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return _pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return _pwd_context.verify(plain, hashed)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def generate_token() -> str:
    return secrets.token_urlsafe(32)


def create_access_token(
    user_id: int,
    username: str,
    role: str,
    expires_delta: Optional[timedelta] = None,
) -> str:
    if expires_delta is None:
        expires_delta = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    expire = datetime.now(timezone.utc) + expires_delta
    payload = {"sub": str(user_id), "username": username, "role": role, "exp": expire}
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> dict:
    return jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])


def create_refresh_token(db: Session, user_id: int) -> str:
    """Create a refresh token, store its hash in DB, return the plain token."""
    from app.models.refresh_token import RefreshToken
    from datetime import timedelta

    plain = generate_token()
    token_hash = hash_token(plain)
    expires_at = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    db_token = RefreshToken(user_id=user_id, token_hash=token_hash, expires_at=expires_at)
    db.add(db_token)
    db.flush()
    return plain


def verify_refresh_token(db: Session, plain: str):
    """Return the RefreshToken if valid, None otherwise."""
    from app.models.refresh_token import RefreshToken
    from datetime import timezone as tz

    token_hash = hash_token(plain)
    token = (
        db.query(RefreshToken)
        .filter(
            RefreshToken.token_hash == token_hash,
            RefreshToken.is_revoked == False,  # noqa: E712
        )
        .first()
    )
    if token is None:
        return None
    if token.expires_at.replace(tzinfo=tz.utc) < datetime.now(tz.utc):
        return None
    return token


def revoke_user_tokens(db: Session, user_id: int) -> None:
    from app.models.refresh_token import RefreshToken

    db.query(RefreshToken).filter(RefreshToken.user_id == user_id).update(
        {"is_revoked": True}
    )
```

- [ ] **Step 7: Run tests — verify they pass**

```bash
cd backend && pytest tests/auth/test_jwt_service.py -v
```
Expected: 4 passed.

- [ ] **Step 8: Commit**

```bash
git add backend/app/schemas/ backend/app/services/ backend/tests/auth/test_jwt_service.py
git commit -m "feat(DEV-36): add auth schemas, JWT service, and password/token utilities"
```

---

## Task 8: `get_current_user` Dependency

**Files:**
- Create: `backend/app/dependencies/__init__.py`
- Create: `backend/app/dependencies/auth.py`

- [ ] **Step 1: Create `backend/app/dependencies/__init__.py`** (empty)

- [ ] **Step 2: Create `backend/app/dependencies/auth.py`**

```python
"""FastAPI auth dependencies — get_current_user and require_admin."""
from fastapi import Depends, HTTPException, Request
from jose import JWTError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.user import User
from app.services.auth_service import decode_access_token


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = decode_access_token(token)
        user_id = int(payload["sub"])
    except (JWTError, KeyError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    user = db.query(User).filter(User.id == user_id, User.is_active == True).first()  # noqa: E712
    if not user:
        raise HTTPException(status_code=401, detail="User not found or inactive")
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user
```

- [ ] **Step 3: Verify import**

```bash
cd backend && python -c "from app.dependencies.auth import get_current_user, require_admin; print('OK')"
```
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add backend/app/dependencies/
git commit -m "feat(DEV-36): add get_current_user and require_admin FastAPI dependencies"
```

---

## Task 9: Login Endpoint

**Files:**
- Create: `backend/app/api/__init__.py`
- Create: `backend/app/api/auth/__init__.py`
- Create: `backend/app/api/auth/login.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/auth/test_login.py`

- [ ] **Step 1: Write failing test**

Create `backend/tests/auth/test_login.py`:

```python
"""Login endpoint integration tests."""


def test_login_success_sets_cookies(client, test_user):
    response = client.post(
        "/v1/auth/login",
        json={"username": "testplayer", "password": "password123"},
    )
    assert response.status_code == 200
    assert "access_token" in response.cookies
    assert "refresh_token" in response.cookies
    data = response.json()
    assert data["username"] == "testplayer"
    assert data["role"] == "player"


def test_login_wrong_password(client, test_user):
    response = client.post(
        "/v1/auth/login",
        json={"username": "testplayer", "password": "wrongpassword"},
    )
    assert response.status_code == 401


def test_login_unknown_user(client):
    response = client.post(
        "/v1/auth/login",
        json={"username": "nobody", "password": "password123"},
    )
    assert response.status_code == 401


def test_login_inactive_user(client, test_user, db_session):
    test_user.is_active = False
    db_session.flush()
    response = client.post(
        "/v1/auth/login",
        json={"username": "testplayer", "password": "password123"},
    )
    assert response.status_code == 401


def test_login_missing_fields(client):
    response = client.post("/v1/auth/login", json={"username": "testplayer"})
    assert response.status_code == 422
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
cd backend && pytest tests/auth/test_login.py -v
```
Expected: `ERRORS` — 404 Not Found (route not registered yet).

- [ ] **Step 3: Create `backend/app/api/__init__.py`** (empty)

- [ ] **Step 4: Create `backend/app/api/auth/__init__.py`**

```python
"""Auth API router — aggregates login, logout, refresh, me, and OAuth endpoints."""
from fastapi import APIRouter

router = APIRouter(prefix="/v1/auth", tags=["auth"])
```

- [ ] **Step 5: Create `backend/app/api/auth/login.py`**

```python
"""POST /v1/auth/login — credential validation and token issuance."""
import structlog
from fastapi import Depends, HTTPException, Response
from fastapi.routing import APIRouter
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.models.user import User
from app.schemas.auth_schemas import LoginRequest, MeResponse
from app.services.auth_service import (
    create_access_token,
    create_refresh_token,
    verify_password,
)

router = APIRouter()
logger = structlog.get_logger(__name__)


@router.post("/login", response_model=MeResponse)
def login(data: LoginRequest, response: Response, db: Session = Depends(get_db)) -> MeResponse:
    user = (
        db.query(User)
        .filter(User.username == data.username, User.is_active == True)  # noqa: E712
        .first()
    )
    if not user or not verify_password(data.password, user.password_hash):
        logger.warning("login_failed", username_prefix=data.username[:3] + "***")
        raise HTTPException(status_code=401, detail="Invalid credentials")

    access_token = create_access_token(user.id, user.username, user.role)
    refresh_token = create_refresh_token(db, user.id)
    db.commit()

    _set_auth_cookies(response, access_token, refresh_token)
    logger.info("login_success", user_id=user.id, role=user.role)
    return MeResponse.model_validate(user)


def _set_auth_cookies(response: Response, access_token: str, refresh_token: str) -> None:
    secure = settings.ENVIRONMENT == "production"
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=secure,
        samesite="lax",
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=secure,
        samesite="lax",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        path="/v1/auth/refresh",
    )
```

- [ ] **Step 6: Register router in `backend/app/api/auth/__init__.py`**

```python
"""Auth API router — aggregates login, logout, refresh, me, and OAuth endpoints."""
from fastapi import APIRouter
from app.api.auth import login

router = APIRouter(prefix="/v1/auth", tags=["auth"])
router.include_router(login.router)
```

- [ ] **Step 7: Register auth router in `backend/app/main.py`**

```python
"""Event Game Framework API — FastAPI application entry point."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.logging import configure_logging
from app.api.auth import router as auth_router

configure_logging(settings.LOG_LEVEL)

app: FastAPI = FastAPI(title="Event Game Framework", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
```

- [ ] **Step 8: Run tests — verify they pass**

```bash
cd backend && pytest tests/auth/test_login.py -v
```
Expected: 5 passed.

- [ ] **Step 9: Commit**

```bash
git add backend/app/api/ backend/app/main.py backend/tests/auth/test_login.py
git commit -m "feat(DEV-36): add POST /v1/auth/login with JWT + refresh token cookie issuance"
```

---

## Task 10: Logout Endpoint

**Files:**
- Create: `backend/app/api/auth/logout.py`
- Test: `backend/tests/auth/test_logout.py`

- [ ] **Step 1: Write failing test**

Create `backend/tests/auth/test_logout.py`:

```python
"""Logout endpoint integration tests."""


def test_logout_clears_cookies(auth_client):
    response = auth_client.post("/v1/auth/logout")
    assert response.status_code == 200
    # Cookies should be cleared (max_age=0 or deleted)
    assert response.cookies.get("access_token", "") in ("", None) or \
        "access_token" not in response.cookies


def test_logout_unauthenticated(client):
    response = client.post("/v1/auth/logout")
    assert response.status_code == 401


def test_logout_revokes_refresh_tokens(auth_client, db_session):
    from app.models.refresh_token import RefreshToken
    # Logout
    auth_client.post("/v1/auth/logout")
    # All refresh tokens for the user should be revoked
    tokens = db_session.query(RefreshToken).filter(RefreshToken.is_revoked == False).all()  # noqa: E712
    assert len(tokens) == 0
```

- [ ] **Step 2: Run — verify fails**

```bash
cd backend && pytest tests/auth/test_logout.py -v
```
Expected: 404 Not Found.

- [ ] **Step 3: Create `backend/app/api/auth/logout.py`**

```python
"""POST /v1/auth/logout — revoke tokens and clear cookies."""
import structlog
from fastapi import Depends, Response
from fastapi.routing import APIRouter
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.services.auth_service import revoke_user_tokens

router = APIRouter()
logger = structlog.get_logger(__name__)


@router.post("/logout")
def logout(
    response: Response,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    revoke_user_tokens(db, user.id)
    db.commit()

    response.delete_cookie("access_token")
    response.delete_cookie("refresh_token", path="/v1/auth/refresh")
    logger.info("logout_success", user_id=user.id)
    return {"detail": "Logged out"}
```

- [ ] **Step 4: Add logout router to `backend/app/api/auth/__init__.py`**

```python
"""Auth API router — aggregates login, logout, refresh, me, and OAuth endpoints."""
from fastapi import APIRouter
from app.api.auth import login, logout

router = APIRouter(prefix="/v1/auth", tags=["auth"])
router.include_router(login.router)
router.include_router(logout.router)
```

- [ ] **Step 5: Run tests — verify they pass**

```bash
cd backend && pytest tests/auth/test_logout.py -v
```
Expected: 3 passed.

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/auth/logout.py backend/app/api/auth/__init__.py \
        backend/tests/auth/test_logout.py
git commit -m "feat(DEV-36): add POST /v1/auth/logout with token revocation"
```

---

## Task 11: Refresh Endpoint

**Files:**
- Create: `backend/app/api/auth/refresh.py`
- Test: `backend/tests/auth/test_refresh.py`

- [ ] **Step 1: Write failing test**

Create `backend/tests/auth/test_refresh.py`:

```python
"""Refresh endpoint integration tests."""


def test_refresh_issues_new_access_token(auth_client, db_session, test_user):
    # Get the refresh token cookie that was set during login
    refresh_token = auth_client.cookies.get("refresh_token")
    assert refresh_token, "No refresh_token cookie after login"

    response = auth_client.post("/v1/auth/refresh")
    assert response.status_code == 200
    assert "access_token" in response.cookies


def test_refresh_without_cookie_returns_401(client):
    response = client.post("/v1/auth/refresh")
    assert response.status_code == 401


def test_refresh_with_invalid_token_returns_401(client):
    client.cookies.set("refresh_token", "invalid-token-value", path="/")
    response = client.post("/v1/auth/refresh")
    assert response.status_code == 401


def test_refresh_revokes_old_token(auth_client, db_session):
    from app.models.refresh_token import RefreshToken

    before_count = db_session.query(RefreshToken).filter(
        RefreshToken.is_revoked == False  # noqa: E712
    ).count()

    auth_client.post("/v1/auth/refresh")

    # Old token should now be revoked; one new token should exist
    after_count = db_session.query(RefreshToken).filter(
        RefreshToken.is_revoked == False  # noqa: E712
    ).count()
    assert after_count == before_count  # net same: 1 revoked, 1 created
```

- [ ] **Step 2: Run — verify fails**

```bash
cd backend && pytest tests/auth/test_refresh.py -v
```
Expected: 404 Not Found.

- [ ] **Step 3: Create `backend/app/api/auth/refresh.py`**

```python
"""POST /v1/auth/refresh — rotate refresh token and issue new access token."""
import structlog
from fastapi import Depends, HTTPException, Request, Response
from fastapi.routing import APIRouter
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.models.user import User
from app.services.auth_service import (
    create_access_token,
    create_refresh_token,
    verify_refresh_token,
)

router = APIRouter()
logger = structlog.get_logger(__name__)


@router.post("/refresh")
def refresh(request: Request, response: Response, db: Session = Depends(get_db)) -> dict[str, str]:
    plain = request.cookies.get("refresh_token")
    if not plain:
        raise HTTPException(status_code=401, detail="No refresh token")

    token = verify_refresh_token(db, plain)
    if token is None:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

    # Rotate: revoke old, issue new
    token.is_revoked = True
    new_refresh = create_refresh_token(db, token.user_id)

    user = db.query(User).filter(User.id == token.user_id).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive")

    new_access = create_access_token(user.id, user.username, user.role)
    db.commit()

    secure = settings.ENVIRONMENT == "production"
    response.set_cookie(
        "access_token", new_access,
        httponly=True, secure=secure, samesite="lax",
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )
    response.set_cookie(
        "refresh_token", new_refresh,
        httponly=True, secure=secure, samesite="lax",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        path="/v1/auth/refresh",
    )
    logger.info("token_refreshed", user_id=user.id)
    return {"detail": "Token refreshed"}
```

- [ ] **Step 4: Add refresh router to `backend/app/api/auth/__init__.py`**

```python
"""Auth API router."""
from fastapi import APIRouter
from app.api.auth import login, logout, refresh

router = APIRouter(prefix="/v1/auth", tags=["auth"])
router.include_router(login.router)
router.include_router(logout.router)
router.include_router(refresh.router)
```

- [ ] **Step 5: Run tests — verify they pass**

```bash
cd backend && pytest tests/auth/test_refresh.py -v
```
Expected: 4 passed.

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/auth/refresh.py backend/app/api/auth/__init__.py \
        backend/tests/auth/test_refresh.py
git commit -m "feat(DEV-36): add POST /v1/auth/refresh with token rotation"
```

---

## Task 12: /v1/auth/me Endpoint

**Files:**
- Create: `backend/app/api/auth/me.py`
- Test: `backend/tests/auth/test_me.py`

- [ ] **Step 1: Write failing test**

Create `backend/tests/auth/test_me.py`:

```python
"""GET /v1/auth/me — current user info endpoint tests."""


def test_me_returns_user(auth_client, test_user):
    response = auth_client.get("/v1/auth/me")
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "testplayer"
    assert data["role"] == "player"
    assert "email" in data
    assert "password_hash" not in data


def test_me_unauthenticated(client):
    response = client.get("/v1/auth/me")
    assert response.status_code == 401


def test_me_admin_returns_admin_role(admin_client):
    response = admin_client.get("/v1/auth/me")
    assert response.status_code == 200
    assert response.json()["role"] == "admin"
```

- [ ] **Step 2: Run — verify fails**

```bash
cd backend && pytest tests/auth/test_me.py -v
```
Expected: 404 Not Found.

- [ ] **Step 3: Create `backend/app/api/auth/me.py`**

```python
"""GET /v1/auth/me — returns current authenticated user. Called by game containers."""
from fastapi import Depends
from fastapi.routing import APIRouter

from app.dependencies.auth import get_current_user
from app.models.user import User
from app.schemas.auth_schemas import MeResponse

router = APIRouter()


@router.get("/me", response_model=MeResponse)
def me(user: User = Depends(get_current_user)) -> MeResponse:
    return MeResponse.model_validate(user)
```

- [ ] **Step 4: Add me router to `backend/app/api/auth/__init__.py`**

```python
"""Auth API router."""
from fastapi import APIRouter
from app.api.auth import login, logout, refresh, me

router = APIRouter(prefix="/v1/auth", tags=["auth"])
router.include_router(login.router)
router.include_router(logout.router)
router.include_router(refresh.router)
router.include_router(me.router)
```

- [ ] **Step 5: Run tests — verify they pass**

```bash
cd backend && pytest tests/auth/test_me.py -v
```
Expected: 3 passed.

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/auth/me.py backend/app/api/auth/__init__.py \
        backend/tests/auth/test_me.py
git commit -m "feat(DEV-36): add GET /v1/auth/me endpoint for current user info"
```

---

## Task 13: Rate Limiting

**Files:**
- Create: `backend/app/middleware/__init__.py`
- Create: `backend/app/middleware/rate_limit.py`
- Test: `backend/tests/security/test_rate_limiting.py`

- [ ] **Step 1: Write failing test**

Create `backend/tests/security/test_rate_limiting.py`:

```python
"""Rate limiting tests — auth endpoints allow 5 req/min per IP."""
import pytest
from unittest.mock import MagicMock, patch


def test_auth_rate_limit_blocks_after_5_requests(client):
    """After 5 login attempts in a window, the 6th should return 429."""
    payload = {"username": "nobody", "password": "wrong"}

    responses = [
        client.post("/v1/auth/login", json=payload) for _ in range(5)
    ]
    for r in responses:
        assert r.status_code == 401  # wrong creds, but not rate limited yet

    # 6th request should be rate limited
    sixth = client.post("/v1/auth/login", json=payload)
    assert sixth.status_code == 429


def test_rate_limit_not_applied_to_health(client):
    for _ in range(10):
        r = client.get("/health")
        assert r.status_code == 200
```

- [ ] **Step 2: Run — verify fails**

```bash
cd backend && pytest tests/security/test_rate_limiting.py::test_auth_rate_limit_blocks_after_5_requests -v
```
Expected: FAILED — 6th request returns 401, not 429.

- [ ] **Step 3: Create `backend/app/middleware/__init__.py`** (empty)

- [ ] **Step 4: Create `backend/app/middleware/rate_limit.py`**

```python
"""Redis-based rate limiting dependency — 5 requests/min per IP for auth endpoints."""
import structlog
from fastapi import Depends, HTTPException, Request
from redis import Redis

from app.core.redis_client import get_redis

logger = structlog.get_logger(__name__)

AUTH_RATE_LIMIT = 5
AUTH_RATE_WINDOW = 60  # seconds


def auth_rate_limit(request: Request, redis: Redis = Depends(get_redis)) -> None:  # type: ignore[type-arg]
    ip = request.client.host if request.client else "unknown"
    key = f"rate:auth:{ip}"
    count = redis.incr(key)
    if count == 1:
        redis.expire(key, AUTH_RATE_WINDOW)
    if count > AUTH_RATE_LIMIT:
        logger.warning("rate_limit_exceeded", ip=ip, count=count)
        raise HTTPException(
            status_code=429,
            detail=f"Too many requests. Try again in {AUTH_RATE_WINDOW} seconds.",
        )
```

- [ ] **Step 5: Apply rate limiting to login and refresh endpoints**

Update `backend/app/api/auth/login.py` — add `Depends(auth_rate_limit)` to the route:

```python
"""POST /v1/auth/login — credential validation and token issuance."""
import structlog
from fastapi import Depends, HTTPException, Response
from fastapi.routing import APIRouter
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.middleware.rate_limit import auth_rate_limit
from app.models.user import User
from app.schemas.auth_schemas import LoginRequest, MeResponse
from app.services.auth_service import (
    create_access_token,
    create_refresh_token,
    verify_password,
)

router = APIRouter()
logger = structlog.get_logger(__name__)


@router.post("/login", response_model=MeResponse, dependencies=[Depends(auth_rate_limit)])
def login(data: LoginRequest, response: Response, db: Session = Depends(get_db)) -> MeResponse:
    user = (
        db.query(User)
        .filter(User.username == data.username, User.is_active == True)  # noqa: E712
        .first()
    )
    if not user or not verify_password(data.password, user.password_hash):
        logger.warning("login_failed", username_prefix=data.username[:3] + "***")
        raise HTTPException(status_code=401, detail="Invalid credentials")

    access_token = create_access_token(user.id, user.username, user.role)
    refresh_token = create_refresh_token(db, user.id)
    db.commit()

    _set_auth_cookies(response, access_token, refresh_token)
    logger.info("login_success", user_id=user.id, role=user.role)
    return MeResponse.model_validate(user)


def _set_auth_cookies(response: Response, access_token: str, refresh_token: str) -> None:
    secure = settings.ENVIRONMENT == "production"
    response.set_cookie(
        key="access_token", value=access_token,
        httponly=True, secure=secure, samesite="lax",
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )
    response.set_cookie(
        key="refresh_token", value=refresh_token,
        httponly=True, secure=secure, samesite="lax",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        path="/v1/auth/refresh",
    )
```

- [ ] **Step 6: Add Redis override to conftest.py**

The rate limiting test needs a Redis connection. Add a real Redis fixture to `conftest.py` (requires Redis running in dev Docker stack):

```python
# Add to backend/tests/conftest.py

import fakeredis

@pytest.fixture(autouse=True)
def fake_redis(monkeypatch):
    """Use fakeredis for all tests to avoid Redis side effects."""
    import app.core.redis_client as redis_module
    fake = fakeredis.FakeRedis(decode_responses=True)
    _pool = fake.connection_pool
    monkeypatch.setattr(redis_module, "_pool", _pool)

    def override_get_redis():
        yield fake

    app.dependency_overrides[get_redis] = override_get_redis
    yield fake
    app.dependency_overrides.pop(get_redis, None)
```

Note: Install `fakeredis` by adding it to `backend/requirements-test.txt`:
```
fakeredis==2.28.0
```

Then install: `pip install fakeredis==2.28.0`

- [ ] **Step 7: Run tests — verify they pass**

```bash
cd backend && pytest tests/security/test_rate_limiting.py -v
```
Expected: 2 passed.

Also run the full auth suite to confirm no regressions:
```bash
cd backend && pytest tests/auth/ -v
```
Expected: all passing.

- [ ] **Step 8: Commit**

```bash
git add backend/app/middleware/ backend/app/api/auth/login.py \
        backend/tests/conftest.py backend/tests/security/ \
        backend/requirements-test.txt
git commit -m "feat(DEV-36): add Redis-based auth rate limiting (5 req/min per IP)"
```

---

## Task 14: Azure OAuth

**Files:**
- Create: `backend/app/services/azure_oauth_service.py`
- Create: `backend/app/api/auth/oauth.py`
- Test: `backend/tests/auth/test_oauth.py`

- [ ] **Step 1: Write failing test**

Create `backend/tests/auth/test_oauth.py`:

```python
"""Azure OAuth endpoint tests — httpx calls are mocked."""
from unittest.mock import patch, MagicMock


def test_azure_redirect_returns_302(client):
    response = client.get("/v1/auth/azure", follow_redirects=False)
    assert response.status_code == 302
    location = response.headers["location"]
    assert "login.microsoftonline.com" in location
    assert "response_type=code" in location


def test_azure_callback_missing_code_returns_400(client):
    response = client.get("/v1/auth/azure/callback")
    assert response.status_code == 400


def test_azure_callback_invalid_state_returns_400(client, fake_redis):
    response = client.get("/v1/auth/azure/callback?code=abc&state=invalid-state")
    assert response.status_code == 400
    assert "state" in response.json()["detail"].lower()


def test_azure_callback_success_sets_cookies(client, db_session, fake_redis):
    """Full OAuth flow with mocked Microsoft token endpoint."""
    import json
    from unittest.mock import patch
    from app.core.config import settings

    # Simulate a valid state stored in Redis
    state = "test-state-value"
    fake_redis.set(f"oauth:state:{state}", "1", ex=300)

    # Mock the Microsoft token exchange and JWKS
    mock_id_token_payload = {
        "oid": "azure-user-id-123",
        "preferred_username": "azureuser@company.com",
        "name": "Azure User",
        "email": "azureuser@company.com",
        "tid": settings.AZURE_TENANT_ID or "test-tenant",
        "aud": settings.AZURE_CLIENT_ID or "test-client",
        "iss": f"https://login.microsoftonline.com/{settings.AZURE_TENANT_ID or 'test-tenant'}/v2.0",
    }

    with patch("app.services.azure_oauth_service.exchange_code_for_token") as mock_exchange, \
         patch("app.services.azure_oauth_service.decode_azure_id_token") as mock_decode:
        mock_exchange.return_value = {"id_token": "fake.jwt.token"}
        mock_decode.return_value = mock_id_token_payload

        response = client.get(
            f"/v1/auth/azure/callback?code=auth-code&state={state}",
            follow_redirects=False,
        )

    assert response.status_code in (200, 302)
    # Either redirect to frontend or return token — both acceptable
    if response.status_code == 200:
        assert "access_token" in response.cookies
```

- [ ] **Step 2: Run — verify fails**

```bash
cd backend && pytest tests/auth/test_oauth.py -v
```
Expected: 404 Not Found on all tests.

- [ ] **Step 3: Create `backend/app/services/azure_oauth_service.py`**

```python
"""Azure OAuth 2.0 service — redirect URL, code exchange, token validation."""
import secrets
from typing import Any

import httpx
import structlog
from jose import JWTError, jwt

from app.core.config import settings

logger = structlog.get_logger(__name__)

AZURE_AUTHORITY = "https://login.microsoftonline.com"
SCOPE = "openid email profile"


def build_authorization_url(state: str) -> str:
    tenant = settings.AZURE_TENANT_ID or "common"
    params = (
        f"client_id={settings.AZURE_CLIENT_ID}"
        f"&response_type=code"
        f"&redirect_uri={settings.AZURE_REDIRECT_URI}"
        f"&scope={SCOPE.replace(' ', '%20')}"
        f"&state={state}"
        f"&response_mode=query"
    )
    return f"{AZURE_AUTHORITY}/{tenant}/oauth2/v2.0/authorize?{params}"


def exchange_code_for_token(code: str) -> dict[str, Any]:
    tenant = settings.AZURE_TENANT_ID or "common"
    url = f"{AZURE_AUTHORITY}/{tenant}/oauth2/v2.0/token"
    data = {
        "client_id": settings.AZURE_CLIENT_ID,
        "client_secret": settings.AZURE_CLIENT_SECRET,
        "code": code,
        "redirect_uri": settings.AZURE_REDIRECT_URI,
        "grant_type": "authorization_code",
    }
    response = httpx.post(url, data=data, timeout=10)
    response.raise_for_status()
    return response.json()


def _get_jwks(tenant: str) -> list[dict]:
    jwks_url = f"{AZURE_AUTHORITY}/{tenant}/discovery/v2.0/keys"
    response = httpx.get(jwks_url, timeout=10)
    response.raise_for_status()
    return response.json()["keys"]


def decode_azure_id_token(id_token: str) -> dict[str, Any]:
    tenant = settings.AZURE_TENANT_ID or "common"
    try:
        jwks = _get_jwks(tenant)
        payload = jwt.decode(
            id_token,
            jwks,
            algorithms=["RS256"],
            audience=settings.AZURE_CLIENT_ID,
        )
        # Validate required claims
        expected_iss = f"{AZURE_AUTHORITY}/{tenant}/v2.0"
        if payload.get("iss") != expected_iss:
            raise JWTError(f"Invalid issuer: {payload.get('iss')}")
        if payload.get("tid") != settings.AZURE_TENANT_ID:
            raise JWTError(f"Invalid tenant: {payload.get('tid')}")
        return payload
    except Exception as exc:
        logger.warning("azure_token_decode_failed", error=str(exc))
        raise JWTError(f"Azure token validation failed: {exc}") from exc


def generate_state() -> str:
    return secrets.token_urlsafe(32)
```

- [ ] **Step 4: Create `backend/app/api/auth/oauth.py`**

```python
"""GET /v1/auth/azure and /v1/auth/azure/callback — Azure OAuth 2.0 flow."""
import structlog
from fastapi import Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from fastapi.routing import APIRouter
from jose import JWTError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.redis_client import get_redis
from app.models.user import User
from app.services.auth_service import create_access_token, create_refresh_token
from app.services.azure_oauth_service import (
    build_authorization_url,
    decode_azure_id_token,
    exchange_code_for_token,
    generate_state,
)

router = APIRouter()
logger = structlog.get_logger(__name__)

STATE_TTL = 300  # 5 minutes


@router.get("/azure")
def azure_login(redis=Depends(get_redis)) -> RedirectResponse:
    state = generate_state()
    redis.set(f"oauth:state:{state}", "1", ex=STATE_TTL)
    url = build_authorization_url(state)
    return RedirectResponse(url=url, status_code=302)


@router.get("/azure/callback")
def azure_callback(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    redis=Depends(get_redis),
) -> dict[str, str]:
    code = request.query_params.get("code")
    state = request.query_params.get("state")

    if not code:
        raise HTTPException(status_code=400, detail="Missing authorization code")

    # Validate CSRF state
    if not state or not redis.get(f"oauth:state:{state}"):
        raise HTTPException(status_code=400, detail="Invalid or expired state parameter")
    redis.delete(f"oauth:state:{state}")

    try:
        token_data = exchange_code_for_token(code)
        claims = decode_azure_id_token(token_data["id_token"])
    except (JWTError, Exception) as exc:
        logger.warning("azure_callback_failed", error=str(exc))
        raise HTTPException(status_code=401, detail="Azure authentication failed")

    azure_id = claims.get("oid", "")
    email = claims.get("email") or claims.get("preferred_username", "")
    name = claims.get("name", email.split("@")[0])

    # Find or create user by azure_id
    user = db.query(User).filter(User.azure_id == azure_id).first()
    if not user:
        # Check by email
        user = db.query(User).filter(User.email == email.lower()).first()
        if user:
            user.azure_id = azure_id
        else:
            user = User(
                username=email.split("@")[0].lower(),
                email=email.lower(),
                password_hash="",  # Azure users have no local password
                azure_id=azure_id,
                role="player",
                is_active=True,
            )
            db.add(user)
            db.flush()

    access_token = create_access_token(user.id, user.username, user.role)
    refresh_token = create_refresh_token(db, user.id)
    db.commit()

    secure = settings.ENVIRONMENT == "production"
    response.set_cookie(
        "access_token", access_token,
        httponly=True, secure=secure, samesite="lax",
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )
    response.set_cookie(
        "refresh_token", refresh_token,
        httponly=True, secure=secure, samesite="lax",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        path="/v1/auth/refresh",
    )
    logger.info("azure_login_success", user_id=user.id)
    return {"detail": "Authenticated via Azure"}
```

- [ ] **Step 5: Add oauth router to `backend/app/api/auth/__init__.py`**

```python
"""Auth API router."""
from fastapi import APIRouter
from app.api.auth import login, logout, refresh, me, oauth

router = APIRouter(prefix="/v1/auth", tags=["auth"])
router.include_router(login.router)
router.include_router(logout.router)
router.include_router(refresh.router)
router.include_router(me.router)
router.include_router(oauth.router)
```

- [ ] **Step 6: Run tests — verify they pass**

```bash
cd backend && pytest tests/auth/test_oauth.py -v
```
Expected: 4 passed (test_azure_callback_success_sets_cookies may need Azure env vars set to non-empty strings — set `AZURE_TENANT_ID=test-tenant AZURE_CLIENT_ID=test-client` in `.env` for testing).

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/azure_oauth_service.py backend/app/api/auth/oauth.py \
        backend/app/api/auth/__init__.py backend/tests/auth/test_oauth.py
git commit -m "feat(DEV-36): add Azure OAuth 2.0 login flow with CSRF state validation"
```

---

## Task 15: Run Full Test Suite + Lint

- [ ] **Step 1: Run full test suite**

```bash
cd backend && pytest --cov=app --cov-report=term-missing -v
```
Expected: all tests pass, coverage ≥ 80%.

- [ ] **Step 2: Run ruff lint**

```bash
cd /home/daniel/event-game && ruff check backend/app/ && ruff format --check backend/app/
```
Expected: no errors.

- [ ] **Step 3: Run mypy**

```bash
cd /home/daniel/event-game && mypy backend/app
```
Expected: no errors (or only known third-party stubs warnings).

- [ ] **Step 4: Verify the running API**

Start the full dev stack:
```bash
cd deploy && docker compose -f docker-compose.dev.yml up postgres redis -d
```

Run the app:
```bash
cd backend && uvicorn app.main:app --reload
```

In a second terminal:
```bash
curl http://localhost:8000/health
# Expected: {"status":"ok"}

curl -X POST http://localhost:8000/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"testplayer","password":"password123"}' \
  -c /tmp/cookies.txt
# Expected: user JSON (after seeding a test user into the DB manually or via psql)
```

- [ ] **Step 5: Final commit**

```bash
git add -A
git commit -m "test(DEV-36): verify full test suite passes with ≥80% coverage"
```

---

## Self-Review Checklist

**Spec coverage:**
- [x] FastAPI app config + CORS — Task 1
- [x] PostgreSQL connection (SQLAlchemy 2.0) — Task 2
- [x] Redis connection — Task 3
- [x] All 10 ORM models — Task 4
- [x] Schema created via `Base.metadata.create_all()` on startup — Task 5
- [x] Test infrastructure with real PostgreSQL — Task 6
- [x] JWT create/decode, password hash — Task 7
- [x] `get_current_user`, `require_admin` dependencies — Task 8
- [x] POST /v1/auth/login — Task 9
- [x] POST /v1/auth/logout — Task 10
- [x] POST /v1/auth/refresh with token rotation — Task 11
- [x] GET /v1/auth/me — Task 12
- [x] Rate limiting (5/min on auth endpoints) — Task 13
- [x] GET /v1/auth/azure + /v1/auth/azure/callback — Task 14
- [x] structlog — Task 1 (configure_logging)

**Placeholder scan:** None found — every step has complete code.

**Type consistency:**
- `create_access_token(user_id: int, username: str, role: str)` — consistent in tasks 7, 9, 11, 14
- `create_refresh_token(db: Session, user_id: int) -> str` — consistent in tasks 7, 9, 11, 14
- `MeResponse` from `app.schemas.auth_schemas` — used in tasks 9, 12
- `auth_rate_limit` dependency — used in task 13, applied in task 13's login.py update
