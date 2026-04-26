# Community Extension Ecosystem Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the full community extension ecosystem — slug-based game identification, progress milestone API, frontend theme/language loading, Docker volume mounts, game validation script, and community repo templates for games, themes, language packs, and events.

**Architecture:** Backend adds a `games` table (slug-keyed) and `game_progress` table (team milestone tracking) with two new API endpoints. Frontend loads community themes (CSS custom properties via `data-theme`) and language packs (JSON merged with event `ui_text`) at runtime from Nginx-served volume mounts. Four community repositories each contain an annotated template and GitHub Actions CI.

**Tech Stack:** Python 3.12 / FastAPI / SQLAlchemy 2.0 / Alembic / PostgreSQL / structlog; React 19 / TypeScript / Vitest / React Testing Library; Nginx volume mounts; bash (validation script).

**Prerequisites:**
- DEV-15: FastAPI backend scaffolded (`backend/app/main.py`, `backend/app/models/base.py`, `backend/app/core/database.py`, `backend/app/core/auth.py`)
- DEV-16: Alembic configured (`backend/alembic/`)
- DEV-17: React frontend scaffolded (`frontend/src/main.tsx`, Vite)
- DEV-18: Dev Dockerfiles and `deploy/docker-compose.dev.yml` exist

---

## File Map

### New backend files
- `backend/app/models/game.py` — Game ORM model (slug, image, milestones, hints, dependencies)
- `backend/app/models/game_progress.py` — GameProgress ORM model (team milestone + completion state)
- `backend/app/schemas/game_schemas.py` — Pydantic request/response schemas
- `backend/app/services/game_service.py` — Game lookup by slug, milestone recording, answer check
- `backend/app/api/games/__init__.py` — Games router aggregation
- `backend/app/api/games/progress.py` — POST /v1/games/{slug}/progress
- `backend/app/api/games/submission.py` — POST /v1/games/{slug}/submit

### New backend tests
- `backend/tests/games/test_progress.py`
- `backend/tests/games/test_submission.py`

### Modified backend files
- `backend/app/main.py` — include games router
- `backend/app/seeds/game_loader.py` — validate slug, image, milestones in YAML
- `backend/app/seeds/seed_games.py` — map new game YAML fields to Game model

### New frontend files
- `frontend/src/services/extensionApi.ts` — fetch theme CSS, fetch lang JSON
- `frontend/src/services/extensionApi.test.ts`
- `frontend/src/hooks/useTheme.ts` — inject CSS, set data-theme on html element
- `frontend/src/hooks/useTheme.test.ts`
- `frontend/src/hooks/useLang.ts` — fetch lang pack, deep-merge with event ui_text
- `frontend/src/hooks/useLang.test.ts`
- `frontend/src/providers/ExtensionProvider/index.tsx` — wraps app, loads theme + lang on mount
- `frontend/src/providers/ExtensionProvider/ExtensionProvider.test.tsx`

### Modified frontend files
- `frontend/src/main.tsx` — wrap root with ExtensionProvider

### Modified deploy files
- `deploy/docker-stack.prod.yml` — volume mounts for themes/ and langs/
- `deploy/docker-compose.dev.yml` — volume mounts for themes/ and langs/

### New files (deploy)
- `deploy/themes/.gitkeep`
- `deploy/langs/.gitkeep`
- `scripts/validate-game.sh`

### Community repo files (separate repositories — Tasks 15–18)
- `event-game-games/template/` — minimal working game implementing full contract
- `event-game-themes/template/theme.css` — annotated CSS with all required tokens
- `event-game-langs/template.json` — annotated JSON with all required keys
- `event-game-events/template.yml` — annotated event YAML with all sections

---

## Task 1: Game ORM model

**Files:**
- Create: `backend/app/models/game.py`
- Create: `backend/tests/games/__init__.py`
- Create: `backend/tests/games/test_progress.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/games/test_progress.py
import pytest
from app.models.game import Game


def test_game_model_has_slug(db_session):
    game = Game(
        event_id=1,
        slug="slide-puzzle",
        title="Find Ishmael",
        description="Rearrange tiles",
        category="puzzle",
        points=100,
        image="ghcr.io/event-game-games/slide-puzzle:1.0.0",
        url="https://events.example.com/games/slide-puzzle",
        milestones=[],
        hints=[],
        dependencies=[],
    )
    db_session.add(game)
    db_session.commit()
    assert game.id is not None
    assert game.slug == "slide-puzzle"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && pytest tests/games/test_progress.py::test_game_model_has_slug -v
```

Expected: `ImportError: cannot import name 'Game'`

- [ ] **Step 3: Create the Game model**

```python
# backend/app/models/game.py
"""Game ORM model — stores game definitions identified by slug."""
from typing import Optional
from sqlalchemy import String, Text, Integer, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base


class Game(Base):
    __tablename__ = "games"

    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"), index=True)
    slug: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(50))
    points: Mapped[int] = mapped_column(Integer, default=0)
    image: Mapped[str] = mapped_column(String(500))
    solution_answer: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    url: Mapped[str] = mapped_column(String(500))
    milestones: Mapped[list] = mapped_column(JSON, default=list)
    hints: Mapped[list] = mapped_column(JSON, default=list)
    dependencies: Mapped[list] = mapped_column(JSON, default=list)

    progress: Mapped[list["GameProgress"]] = relationship(
        "GameProgress", back_populates="game", cascade="all, delete-orphan"
    )
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd backend && pytest tests/games/test_progress.py::test_game_model_has_slug -v
```

Expected: `PASSED`

- [ ] **Step 5: Commit**

```bash
git add backend/app/models/game.py backend/tests/games/
git commit -m "feat: add Game model with slug-based identification"
```

---

## Task 2: GameProgress ORM model

**Files:**
- Create: `backend/app/models/game_progress.py`
- Modify: `backend/tests/conftest.py` (add test_game fixture)

- [ ] **Step 1: Add test_game fixture to conftest.py**

Add to `backend/tests/conftest.py`:

```python
import pytest
from app.models.game import Game

@pytest.fixture
def test_game(db_session):
    game = Game(
        event_id=1,
        slug="slide-puzzle",
        title="Find Ishmael",
        description="Rearrange tiles",
        category="puzzle",
        points=100,
        image="ghcr.io/event-game-games/slide-puzzle:1.0.0",
        solution_answer="CALL ME ISHMAEL",
        url="https://events.example.com/games/slide-puzzle",
        milestones=[{"id": "website_found", "ai_context": "Found site"}],
        hints=["Start from corners"],
        dependencies=[],
    )
    db_session.add(game)
    db_session.commit()
    return game
```

- [ ] **Step 2: Write the failing test**

Add to `backend/tests/games/test_progress.py`:

```python
def test_game_progress_model(db_session, test_game):
    from app.models.game_progress import GameProgress
    progress = GameProgress(
        game_id=test_game.id,
        team_id=1,
        milestone="website_found",
        is_completed=False,
    )
    db_session.add(progress)
    db_session.commit()
    assert progress.id is not None
    assert progress.milestone == "website_found"
    assert progress.is_completed is False
```

- [ ] **Step 3: Run test to verify it fails**

```bash
cd backend && pytest tests/games/test_progress.py::test_game_progress_model -v
```

Expected: `ImportError: cannot import name 'GameProgress'`

- [ ] **Step 4: Create the GameProgress model**

```python
# backend/app/models/game_progress.py
"""GameProgress model — tracks team milestone progress and completion state per game."""
from datetime import datetime
from typing import Optional
from sqlalchemy import String, ForeignKey, Boolean, DateTime, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base


class GameProgress(Base):
    __tablename__ = "game_progress"
    __table_args__ = (UniqueConstraint("game_id", "team_id", name="uq_game_team"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    game_id: Mapped[int] = mapped_column(ForeignKey("games.id"), index=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), index=True)
    milestone: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    is_completed: Mapped[bool] = mapped_column(Boolean, default=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    submitted_answer: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    game: Mapped["Game"] = relationship("Game", back_populates="progress")
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd backend && pytest tests/games/test_progress.py -v
```

Expected: 2 tests PASSED

- [ ] **Step 6: Commit**

```bash
git add backend/app/models/game_progress.py backend/tests/conftest.py
git commit -m "feat: add GameProgress model with milestone and completion tracking"
```

---

## Task 3: Alembic migration

**Files:**
- Create: `backend/alembic/versions/002_add_games_and_progress.py`

- [ ] **Step 1: Generate migration**

```bash
cd backend && alembic revision --autogenerate -m "add_games_and_progress"
```

Expected: Creates `backend/alembic/versions/002_add_games_and_progress.py`

- [ ] **Step 2: Verify migration creates both tables**

Open the generated file. Confirm `op.create_table("games", ...)` and `op.create_table("game_progress", ...)` are both present. Confirm `games.slug` has a `UniqueConstraint` and `game_progress` has `uq_game_team`.

- [ ] **Step 3: Run migration**

```bash
cd backend && alembic upgrade head
```

Expected: `Running upgrade -> 002_add_games_and_progress, add_games_and_progress`

- [ ] **Step 4: Verify tables exist in PostgreSQL**

```bash
psql $DATABASE_URL -c "\dt" | grep -E "games|game_progress"
```

Expected: Both `games` and `game_progress` in the list.

- [ ] **Step 5: Commit**

```bash
git add backend/alembic/versions/
git commit -m "feat: migration — add games and game_progress tables"
```

---

## Task 4: Game schemas

**Files:**
- Create: `backend/app/schemas/game_schemas.py`

- [ ] **Step 1: Write the failing tests**

Add to `backend/tests/games/test_progress.py`:

```python
def test_progress_request_validates_milestone():
    from app.schemas.game_schemas import ProgressRequest
    req = ProgressRequest(milestone="ssh_connected")
    assert req.milestone == "ssh_connected"


def test_progress_request_rejects_empty_milestone():
    from pydantic import ValidationError
    from app.schemas.game_schemas import ProgressRequest
    with pytest.raises(ValidationError):
        ProgressRequest(milestone="")


def test_submit_request_validates_solution():
    from app.schemas.game_schemas import SubmitRequest
    req = SubmitRequest(solution="CALL ME ISHMAEL")
    assert req.solution == "CALL ME ISHMAEL"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && pytest tests/games/test_progress.py -k "schema" -v
```

Expected: `ImportError: cannot import name 'ProgressRequest'`

- [ ] **Step 3: Create schemas**

```python
# backend/app/schemas/game_schemas.py
"""Pydantic schemas for game progress reporting and answer submission."""
from typing import Optional
from pydantic import BaseModel, Field


class ProgressRequest(BaseModel):
    milestone: str = Field(min_length=1, max_length=100, pattern=r"^[\w_]+$")


class ProgressResponse(BaseModel):
    game_slug: str
    team_id: int
    milestone: str


class SubmitRequest(BaseModel):
    solution: str = Field(min_length=1, max_length=500)


class SubmitResponse(BaseModel):
    correct: bool
    points: Optional[int] = None
    message: str
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend && pytest tests/games/test_progress.py -k "schema" -v
```

Expected: 3 tests PASSED

- [ ] **Step 5: Commit**

```bash
git add backend/app/schemas/game_schemas.py
git commit -m "feat: add Pydantic schemas for game progress and submission"
```

---

## Task 5: Game service

**Files:**
- Create: `backend/app/services/game_service.py`

- [ ] **Step 1: Write the failing tests**

Add to `backend/tests/games/test_progress.py`:

```python
def test_get_game_by_slug_returns_game(db_session, test_game):
    from app.services.game_service import get_game_by_slug
    game = get_game_by_slug(db_session, "slide-puzzle")
    assert game is not None
    assert game.slug == "slide-puzzle"


def test_get_game_by_slug_returns_none_for_unknown(db_session):
    from app.services.game_service import get_game_by_slug
    assert get_game_by_slug(db_session, "nonexistent") is None


def test_record_milestone_creates_progress(db_session, test_game):
    from app.services.game_service import record_milestone
    progress = record_milestone(db_session, game=test_game, team_id=1, milestone="website_found")
    assert progress.milestone == "website_found"
    assert progress.is_completed is False


def test_record_milestone_updates_existing(db_session, test_game):
    from app.services.game_service import record_milestone
    record_milestone(db_session, game=test_game, team_id=1, milestone="website_found")
    progress = record_milestone(db_session, game=test_game, team_id=1, milestone="ssh_connected")
    assert progress.milestone == "ssh_connected"


def test_check_answer_correct(test_game):
    from app.services.game_service import check_answer
    assert check_answer(test_game, "CALL ME ISHMAEL") is True


def test_check_answer_case_insensitive(test_game):
    from app.services.game_service import check_answer
    assert check_answer(test_game, "call me ishmael") is True


def test_check_answer_wrong(test_game):
    from app.services.game_service import check_answer
    assert check_answer(test_game, "wrong answer") is False
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && pytest tests/games/test_progress.py -k "service or get_game or record_milestone or check_answer" -v
```

Expected: `ImportError: cannot import name 'get_game_by_slug'`

- [ ] **Step 3: Create the game service**

```python
# backend/app/services/game_service.py
"""Game service — slug lookup, milestone recording, answer validation."""
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.orm import Session
from app.models.game import Game
from app.models.game_progress import GameProgress


def get_game_by_slug(db: Session, slug: str) -> Optional[Game]:
    return db.query(Game).filter(Game.slug == slug).first()


def get_or_create_progress(db: Session, game: Game, team_id: int) -> GameProgress:
    # SECURITY: Scope all progress to team_id — teams cannot access each other's progress
    progress = db.query(GameProgress).filter_by(game_id=game.id, team_id=team_id).first()
    if not progress:
        progress = GameProgress(game_id=game.id, team_id=team_id)
        db.add(progress)
        db.flush()
    return progress


def record_milestone(db: Session, game: Game, team_id: int, milestone: str) -> GameProgress:
    progress = get_or_create_progress(db, game, team_id)
    progress.milestone = milestone
    db.commit()
    return progress


def check_answer(game: Game, submitted: str) -> bool:
    if not game.solution_answer:
        return False
    return submitted.strip().lower() == game.solution_answer.strip().lower()


def complete_game(db: Session, game: Game, team_id: int, submitted_answer: str) -> GameProgress:
    progress = get_or_create_progress(db, game, team_id)
    progress.is_completed = True
    progress.completed_at = datetime.now(timezone.utc)
    progress.submitted_answer = submitted_answer
    progress.milestone = "completed"
    db.commit()
    return progress
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend && pytest tests/games/test_progress.py -v
```

Expected: All tests PASSED

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/game_service.py
git commit -m "feat: add game service — slug lookup, milestone recording, answer check"
```

---

## Task 6: Progress API endpoint

**Files:**
- Create: `backend/app/api/games/__init__.py`
- Create: `backend/app/api/games/progress.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: Write the failing tests**

Add to `backend/tests/games/test_progress.py`:

```python
def test_post_progress_records_milestone(auth_client, db_session, test_game):
    response = auth_client.post(
        f"/v1/games/{test_game.slug}/progress",
        json={"milestone": "website_found"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["milestone"] == "website_found"
    assert data["game_slug"] == "slide-puzzle"


def test_post_progress_returns_404_for_unknown_game(auth_client):
    response = auth_client.post(
        "/v1/games/nonexistent/progress",
        json={"milestone": "website_found"},
    )
    assert response.status_code == 404


def test_post_progress_requires_auth(client):
    response = client.post(
        "/v1/games/slide-puzzle/progress",
        json={"milestone": "website_found"},
    )
    assert response.status_code == 401
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && pytest tests/games/test_progress.py -k "post_progress" -v
```

Expected: `404 NOT FOUND` (route does not exist yet)

- [ ] **Step 3: Create router and progress endpoint**

```python
# backend/app/api/games/__init__.py
"""Games API router — progress reporting and answer submission."""
from fastapi import APIRouter
from app.api.games.progress import router as progress_router
from app.api.games.submission import router as submission_router

router = APIRouter(prefix="/v1/games", tags=["games"])
router.include_router(progress_router)
router.include_router(submission_router)
```

```python
# backend/app/api/games/progress.py
"""Progress endpoint — game containers report which milestone the player reached."""
import structlog
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.auth import get_current_user
from app.models.user import User
from app.schemas.game_schemas import ProgressRequest, ProgressResponse
from app.services.game_service import get_game_by_slug, record_milestone

logger = structlog.get_logger(__name__)
router = APIRouter()


@router.post("/{slug}/progress", response_model=ProgressResponse)
async def report_progress(
    slug: str,
    body: ProgressRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    game = get_game_by_slug(db, slug)
    if not game:
        raise HTTPException(status_code=404, detail=f"Game '{slug}' not found")

    progress = record_milestone(db, game=game, team_id=current_user.team_id, milestone=body.milestone)
    logger.info("milestone_recorded", game_slug=slug, team_id=current_user.team_id, milestone=body.milestone)

    return ProgressResponse(game_slug=slug, team_id=current_user.team_id, milestone=progress.milestone)
```

- [ ] **Step 4: Register games router in main.py**

Add to `backend/app/main.py`:

```python
from app.api.games import router as games_router
app.include_router(games_router)
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd backend && pytest tests/games/test_progress.py -k "post_progress" -v
```

Expected: 3 tests PASSED

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/games/ backend/app/main.py
git commit -m "feat: add POST /v1/games/{slug}/progress endpoint"
```

---

## Task 7: Submit API endpoint

**Files:**
- Create: `backend/app/api/games/submission.py`
- Create: `backend/tests/games/test_submission.py`

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/games/test_submission.py
import pytest
from app.models.game import Game


@pytest.fixture
def test_game_with_answer(db_session):
    game = Game(
        event_id=1,
        slug="slide-puzzle",
        title="Find Ishmael",
        description="Rearrange tiles",
        category="puzzle",
        points=100,
        image="ghcr.io/event-game-games/slide-puzzle:1.0.0",
        solution_answer="CALL ME ISHMAEL",
        url="https://events.example.com/games/slide-puzzle",
        milestones=[],
        hints=[],
        dependencies=[],
    )
    db_session.add(game)
    db_session.commit()
    return game


def test_submit_correct_answer(auth_client, test_game_with_answer):
    response = auth_client.post(
        f"/v1/games/{test_game_with_answer.slug}/submit",
        json={"solution": "CALL ME ISHMAEL"},
    )
    assert response.status_code == 200
    assert response.json()["correct"] is True
    assert response.json()["points"] == 100


def test_submit_wrong_answer(auth_client, test_game_with_answer):
    response = auth_client.post(
        f"/v1/games/{test_game_with_answer.slug}/submit",
        json={"solution": "wrong answer"},
    )
    assert response.status_code == 200
    assert response.json()["correct"] is False
    assert response.json()["points"] is None


def test_submit_case_insensitive(auth_client, test_game_with_answer):
    response = auth_client.post(
        f"/v1/games/{test_game_with_answer.slug}/submit",
        json={"solution": "call me ishmael"},
    )
    assert response.status_code == 200
    assert response.json()["correct"] is True


def test_submit_already_completed_returns_409(auth_client, test_game_with_answer):
    auth_client.post(
        f"/v1/games/{test_game_with_answer.slug}/submit",
        json={"solution": "CALL ME ISHMAEL"},
    )
    response = auth_client.post(
        f"/v1/games/{test_game_with_answer.slug}/submit",
        json={"solution": "CALL ME ISHMAEL"},
    )
    assert response.status_code == 409
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && pytest tests/games/test_submission.py -v
```

Expected: `404 NOT FOUND` (route does not exist yet)

- [ ] **Step 3: Create the submission endpoint**

```python
# backend/app/api/games/submission.py
"""Submission endpoint — validates the team's answer and marks the game complete."""
import structlog
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.auth import get_current_user
from app.models.user import User
from app.schemas.game_schemas import SubmitRequest, SubmitResponse
from app.services.game_service import (
    get_game_by_slug,
    get_or_create_progress,
    check_answer,
    complete_game,
)

logger = structlog.get_logger(__name__)
router = APIRouter()


@router.post("/{slug}/submit", response_model=SubmitResponse)
async def submit_answer(
    slug: str,
    body: SubmitRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    game = get_game_by_slug(db, slug)
    if not game:
        raise HTTPException(status_code=404, detail=f"Game '{slug}' not found")

    # SECURITY: Scope to team — prevent a user from submitting for another team
    progress = get_or_create_progress(db, game, current_user.team_id)
    if progress.is_completed:
        raise HTTPException(status_code=409, detail="Your team has already completed this game")

    if check_answer(game, body.solution):
        complete_game(db, game, current_user.team_id, body.solution)
        logger.info("game_completed", game_slug=slug, team_id=current_user.team_id)
        return SubmitResponse(correct=True, points=game.points, message="Correct! Well done.")

    logger.info("wrong_answer_submitted", game_slug=slug, team_id=current_user.team_id)
    return SubmitResponse(correct=False, message="Incorrect answer. Keep trying!")
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend && pytest tests/games/test_submission.py -v
```

Expected: 4 tests PASSED

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/games/submission.py backend/tests/games/test_submission.py
git commit -m "feat: add POST /v1/games/{slug}/submit with slug-based identification and 409 guard"
```

---

## Task 8: Event YAML parser — new game block fields

**Files:**
- Modify: `backend/app/seeds/game_loader.py`
- Modify: `backend/app/seeds/seed_games.py`

- [ ] **Step 1: Write the failing tests**

Add to `backend/tests/games/test_progress.py`:

```python
def test_yaml_validator_accepts_valid_game_block():
    from app.seeds.game_loader import validate_yaml_structure
    data = {
        "event": {"year": 2026, "title": "Test", "is_active": True},
        "games": [{"slug": "slide-puzzle", "title": "Find Ishmael",
                   "image": "ghcr.io/event-game-games/slide-puzzle:1.0.0",
                   "milestones": [{"id": "found", "ai_context": "Found"}]}],
    }
    validate_yaml_structure(data, "test.yml")  # must not raise


def test_yaml_validator_rejects_missing_slug():
    from app.seeds.game_loader import validate_yaml_structure
    data = {
        "event": {"year": 2026, "title": "Test"},
        "games": [{"title": "No Slug", "image": "ghcr.io/org/game:1.0.0"}],
    }
    with pytest.raises(ValueError, match="slug"):
        validate_yaml_structure(data, "test.yml")


def test_yaml_validator_rejects_missing_image():
    from app.seeds.game_loader import validate_yaml_structure
    data = {
        "event": {"year": 2026, "title": "Test"},
        "games": [{"slug": "my-game", "title": "No Image"}],
    }
    with pytest.raises(ValueError, match="image"):
        validate_yaml_structure(data, "test.yml")
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && pytest tests/games/test_progress.py -k "yaml_validator" -v
```

Expected: `FAILED` — validator does not check slug or image yet

- [ ] **Step 3: Update validate_yaml_structure in game_loader.py**

Replace the `validate_yaml_structure` function in `backend/app/seeds/game_loader.py`:

```python
def validate_yaml_structure(data: Dict[str, Any], yaml_filename: str) -> None:
    """Validate YAML including new required game fields: slug, image, milestones."""
    required_sections = ["event", "games"]
    for section in required_sections:
        if section not in data:
            raise ValueError(f"Missing required section '{section}' in {yaml_filename}")

    event = data["event"]
    for field in ["year", "title"]:
        if field not in event:
            raise ValueError(f"Missing required field 'event.{field}' in {yaml_filename}")

    games = data["games"]
    if not isinstance(games, list) or len(games) == 0:
        raise ValueError(f"'games' must be a non-empty list in {yaml_filename}")

    for i, game in enumerate(games):
        for field in ["slug", "image"]:
            if field not in game:
                raise ValueError(f"Game {i} missing required field '{field}' in {yaml_filename}")
        if not isinstance(game.get("milestones", []), list):
            raise ValueError(f"Game {i} 'milestones' must be a list in {yaml_filename}")
```

- [ ] **Step 4: Update seed_games.py to map new fields**

In `backend/app/seeds/seed_games.py`, update the function that creates a Game from YAML data:

```python
def seed_game_from_yaml_data(db: Session, event_id: int, game_data: dict) -> "Game":
    from app.models.game import Game
    game = Game(
        event_id=event_id,
        slug=game_data["slug"],
        title=game_data.get("title", game_data["slug"]),
        description=game_data.get("description", ""),
        category=game_data.get("category", "general"),
        points=game_data.get("points", 0),
        image=game_data["image"],
        solution_answer=game_data.get("solution_answer"),
        url=game_data.get("url", ""),
        milestones=game_data.get("milestones", []),
        hints=game_data.get("hints", []),
        dependencies=game_data.get("dependencies", []),
    )
    db.add(game)
    db.flush()
    return game
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd backend && pytest tests/games/test_progress.py -k "yaml_validator" -v
```

Expected: 3 tests PASSED

- [ ] **Step 6: Commit**

```bash
git add backend/app/seeds/game_loader.py backend/app/seeds/seed_games.py
git commit -m "feat: YAML parser validates and maps slug, image, milestones per game block"
```

---

## Task 9: Frontend extension API service

**Files:**
- Create: `frontend/src/services/extensionApi.ts`
- Create: `frontend/src/services/extensionApi.test.ts`

- [ ] **Step 1: Write the failing tests**

```typescript
// frontend/src/services/extensionApi.test.ts
import { describe, it, expect, vi, beforeEach } from "vitest"
import { fetchThemeCss, fetchLangPack } from "./extensionApi"

beforeEach(() => vi.resetAllMocks())

describe("fetchThemeCss", () => {
  it("returns css text for a valid theme", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      text: () => Promise.resolve("[data-theme='cyberpunk'] { --primary: red; }"),
    } as Response)
    const css = await fetchThemeCss("cyberpunk")
    expect(css).toContain("--primary")
    expect(fetch).toHaveBeenCalledWith("/themes/cyberpunk/theme.css")
  })

  it("throws when theme not found", async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 404 } as Response)
    await expect(fetchThemeCss("missing")).rejects.toThrow("Theme 'missing' not found")
  })
})

describe("fetchLangPack", () => {
  it("returns parsed JSON for valid locale", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ login: { submitButton: "Anmelden" } }),
    } as Response)
    const lang = await fetchLangPack("de")
    expect((lang.login as Record<string, string>).submitButton).toBe("Anmelden")
    expect(fetch).toHaveBeenCalledWith("/langs/de.json")
  })

  it("throws when lang pack not found", async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 404 } as Response)
    await expect(fetchLangPack("xx")).rejects.toThrow("Language pack 'xx' not found")
  })
})
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd frontend && npm run test:run -- src/services/extensionApi.test.ts
```

Expected: `Cannot find module './extensionApi'`

- [ ] **Step 3: Create the service**

```typescript
// frontend/src/services/extensionApi.ts
// Fetches community theme CSS and language pack JSON from Nginx-served volume mounts

export async function fetchThemeCss(themeName: string): Promise<string> {
  const response = await fetch(`/themes/${themeName}/theme.css`)
  if (!response.ok) {
    throw new Error(`Theme '${themeName}' not found (HTTP ${response.status})`)
  }
  return response.text()
}

export async function fetchLangPack(locale: string): Promise<Record<string, unknown>> {
  const response = await fetch(`/langs/${locale}.json`)
  if (!response.ok) {
    throw new Error(`Language pack '${locale}' not found (HTTP ${response.status})`)
  }
  return response.json()
}
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd frontend && npm run test:run -- src/services/extensionApi.test.ts
```

Expected: 4 tests PASSED

- [ ] **Step 5: Commit**

```bash
git add frontend/src/services/extensionApi.ts frontend/src/services/extensionApi.test.ts
git commit -m "feat: add extensionApi service — fetch theme CSS and lang JSON from Nginx"
```

---

## Task 10: useTheme hook

**Files:**
- Create: `frontend/src/hooks/useTheme.ts`
- Create: `frontend/src/hooks/useTheme.test.ts`

- [ ] **Step 1: Write the failing tests**

```typescript
// frontend/src/hooks/useTheme.test.ts
import { renderHook, waitFor } from "@testing-library/react"
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest"
import { useTheme } from "./useTheme"
import * as extensionApi from "../services/extensionApi"

beforeEach(() => {
  vi.spyOn(extensionApi, "fetchThemeCss").mockResolvedValue(
    "[data-theme='cyberpunk'] { --primary: red; }"
  )
})

afterEach(() => {
  document.documentElement.removeAttribute("data-theme")
  document.head.querySelectorAll("style[data-theme-id]").forEach((el) => el.remove())
})

describe("useTheme", () => {
  it("sets data-theme attribute on html element", async () => {
    renderHook(() => useTheme("cyberpunk"))
    await waitFor(() => {
      expect(document.documentElement.getAttribute("data-theme")).toBe("cyberpunk")
    })
  })

  it("injects a style tag with theme CSS", async () => {
    renderHook(() => useTheme("cyberpunk"))
    await waitFor(() => {
      const style = document.head.querySelector("style[data-theme-id='cyberpunk']")
      expect(style).not.toBeNull()
      expect(style?.textContent).toContain("--primary")
    })
  })

  it("does nothing when theme is undefined", async () => {
    renderHook(() => useTheme(undefined))
    await waitFor(() => {
      expect(document.documentElement.getAttribute("data-theme")).toBeNull()
    })
  })
})
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd frontend && npm run test:run -- src/hooks/useTheme.test.ts
```

Expected: `Cannot find module './useTheme'`

- [ ] **Step 3: Create the hook**

```typescript
// frontend/src/hooks/useTheme.ts
// Fetches community theme CSS and applies it by injecting a <style> tag and setting data-theme
import { useEffect } from "react"
import { fetchThemeCss } from "../services/extensionApi"

export function useTheme(themeName: string | undefined): void {
  useEffect(() => {
    if (!themeName) return
    fetchThemeCss(themeName)
      .then((css) => {
        let style = document.head.querySelector<HTMLStyleElement>(
          `style[data-theme-id="${themeName}"]`
        )
        if (!style) {
          style = document.createElement("style")
          style.setAttribute("data-theme-id", themeName)
          document.head.appendChild(style)
        }
        style.textContent = css
        document.documentElement.setAttribute("data-theme", themeName)
      })
      .catch((err) => console.error(`Failed to load theme '${themeName}':`, err))
  }, [themeName])
}
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd frontend && npm run test:run -- src/hooks/useTheme.test.ts
```

Expected: 3 tests PASSED

- [ ] **Step 5: Commit**

```bash
git add frontend/src/hooks/useTheme.ts frontend/src/hooks/useTheme.test.ts
git commit -m "feat: add useTheme hook — fetches and injects community theme CSS"
```

---

## Task 11: useLang hook

**Files:**
- Create: `frontend/src/hooks/useLang.ts`
- Create: `frontend/src/hooks/useLang.test.ts`

- [ ] **Step 1: Write the failing tests**

```typescript
// frontend/src/hooks/useLang.test.ts
import { renderHook, waitFor } from "@testing-library/react"
import { describe, it, expect, vi, beforeEach } from "vitest"
import { useLang } from "./useLang"
import * as extensionApi from "../services/extensionApi"

beforeEach(() => {
  vi.spyOn(extensionApi, "fetchLangPack").mockResolvedValue({
    nav: { games: "Games" },
    login: { submitButton: "Login" },
  })
})

describe("useLang", () => {
  it("returns event text override merged over base lang", async () => {
    const { result } = renderHook(() =>
      useLang("de", { nav: { games: "Spiele" } })
    )
    await waitFor(() => {
      expect((result.current.nav as Record<string, string>)?.games).toBe("Spiele")
      expect((result.current.login as Record<string, string>)?.submitButton).toBe("Login")
    })
  })

  it("returns base lang when no event text overrides", async () => {
    const { result } = renderHook(() => useLang("de", {}))
    await waitFor(() => {
      expect((result.current.nav as Record<string, string>)?.games).toBe("Games")
    })
  })

  it("returns empty object before lang loads", () => {
    const { result } = renderHook(() => useLang("de", {}))
    expect(result.current).toEqual({})
  })
})
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd frontend && npm run test:run -- src/hooks/useLang.test.ts
```

Expected: `Cannot find module './useLang'`

- [ ] **Step 3: Create the hook**

```typescript
// frontend/src/hooks/useLang.ts
// Fetches community lang pack and deep-merges with event-specific ui_text overrides
import { useState, useEffect } from "react"
import { fetchLangPack } from "../services/extensionApi"

type LangData = Record<string, unknown>

function deepMerge(base: LangData, override: LangData): LangData {
  const result = { ...base }
  for (const key of Object.keys(override)) {
    const b = base[key]
    const o = override[key]
    if (b && o && typeof b === "object" && typeof o === "object" && !Array.isArray(b)) {
      result[key] = deepMerge(b as LangData, o as LangData)
    } else {
      result[key] = o
    }
  }
  return result
}

export function useLang(locale: string, eventText: LangData): LangData {
  const [lang, setLang] = useState<LangData>({})

  useEffect(() => {
    fetchLangPack(locale)
      .then((base) => setLang(deepMerge(base as LangData, eventText)))
      .catch((err) => console.error(`Failed to load lang pack '${locale}':`, err))
  }, [locale])

  return lang
}
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd frontend && npm run test:run -- src/hooks/useLang.test.ts
```

Expected: 3 tests PASSED

- [ ] **Step 5: Commit**

```bash
git add frontend/src/hooks/useLang.ts frontend/src/hooks/useLang.test.ts
git commit -m "feat: add useLang hook — fetches lang pack and deep-merges with event ui_text"
```

---

## Task 12: ExtensionProvider component

**Files:**
- Create: `frontend/src/providers/ExtensionProvider/index.tsx`
- Create: `frontend/src/providers/ExtensionProvider/ExtensionProvider.test.tsx`
- Modify: `frontend/src/main.tsx`

- [ ] **Step 1: Write the failing tests**

```typescript
// frontend/src/providers/ExtensionProvider/ExtensionProvider.test.tsx
import { render, screen, waitFor } from "@testing-library/react"
import { describe, it, expect, vi } from "vitest"
import { ExtensionProvider } from "./index"
import * as extensionApi from "../../services/extensionApi"

vi.spyOn(extensionApi, "fetchThemeCss").mockResolvedValue(
  "[data-theme='cyberpunk'] { --primary: red; }"
)
vi.spyOn(extensionApi, "fetchLangPack").mockResolvedValue({ nav: { games: "Spiele" } })

describe("ExtensionProvider", () => {
  it("renders children", () => {
    render(
      <ExtensionProvider theme="cyberpunk" locale="de" eventText={{}}>
        <div>content</div>
      </ExtensionProvider>
    )
    expect(screen.getByText("content")).toBeInTheDocument()
  })

  it("applies theme to html element", async () => {
    render(
      <ExtensionProvider theme="cyberpunk" locale="de" eventText={{}}>
        <div />
      </ExtensionProvider>
    )
    await waitFor(() => {
      expect(document.documentElement.getAttribute("data-theme")).toBe("cyberpunk")
    })
  })
})
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd frontend && npm run test:run -- src/providers/ExtensionProvider/ExtensionProvider.test.tsx
```

Expected: `Cannot find module './index'`

- [ ] **Step 3: Create ExtensionProvider**

```typescript
// frontend/src/providers/ExtensionProvider/index.tsx
// Wraps the app root — loads community theme CSS and language pack on mount
import { createContext, useContext, ReactNode } from "react"
import { useTheme } from "../../hooks/useTheme"
import { useLang } from "../../hooks/useLang"

type LangData = Record<string, unknown>

interface ExtensionContextValue {
  lang: LangData
}

const ExtensionContext = createContext<ExtensionContextValue>({ lang: {} })

export function useExtension(): ExtensionContextValue {
  return useContext(ExtensionContext)
}

interface Props {
  theme: string | undefined
  locale: string
  eventText: LangData
  children: ReactNode
}

export function ExtensionProvider({ theme, locale, eventText, children }: Props) {
  useTheme(theme)
  const lang = useLang(locale, eventText)
  return (
    <ExtensionContext.Provider value={{ lang }}>
      {children}
    </ExtensionContext.Provider>
  )
}
```

- [ ] **Step 4: Wrap root in ExtensionProvider in main.tsx**

```typescript
// frontend/src/main.tsx
import { StrictMode } from "react"
import { createRoot } from "react-dom/client"
import { ExtensionProvider } from "./providers/ExtensionProvider"
import App from "./App"

// Runtime config injected by the backend into index.html via a <script> block
const config = (window as Window & { __EVENT_CONFIG__?: Record<string, unknown> }).__EVENT_CONFIG__ ?? {}
const theme = config.theme as string | undefined
const locale = (config.language as string | undefined) ?? "en"
const eventText = ((config.ui_text as Record<string, unknown> | undefined)?.[locale] ?? {}) as Record<string, unknown>

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <ExtensionProvider theme={theme} locale={locale} eventText={eventText}>
      <App />
    </ExtensionProvider>
  </StrictMode>
)
```

- [ ] **Step 5: Run all frontend tests**

```bash
cd frontend && npm run test:run
```

Expected: All tests PASSED

- [ ] **Step 6: Commit**

```bash
git add frontend/src/providers/ frontend/src/main.tsx
git commit -m "feat: add ExtensionProvider — loads theme and lang pack on app mount"
```

---

## Task 13: Docker volume mounts

**Files:**
- Modify: `deploy/docker-stack.prod.yml`
- Modify: `deploy/docker-compose.dev.yml`
- Create: `deploy/themes/.gitkeep`
- Create: `deploy/langs/.gitkeep`

- [ ] **Step 1: Add volume mounts to docker-stack.prod.yml**

Add `volumes` to the `frontend` service:

```yaml
services:
  frontend:
    image: ghcr.io/${IMAGE_OWNER}/event-game-frontend:${IMAGE_TAG}
    volumes:
      - ./themes:/usr/share/nginx/html/themes:ro
      - ./langs:/usr/share/nginx/html/langs:ro
    networks:
      - event-game-internal
```

- [ ] **Step 2: Add volume mounts to docker-compose.dev.yml**

Add `volumes` to the `frontend` service:

```yaml
services:
  frontend:
    build:
      context: ../frontend
      dockerfile: Dockerfile.dev
    volumes:
      - ./themes:/usr/share/nginx/html/themes:ro
      - ./langs:/usr/share/nginx/html/langs:ro
```

- [ ] **Step 3: Create placeholder directories**

```bash
mkdir -p deploy/themes deploy/langs
touch deploy/themes/.gitkeep deploy/langs/.gitkeep
```

- [ ] **Step 4: Verify dev stack serves theme path**

```bash
cd deploy && docker compose up frontend -d
curl -I http://localhost/themes/
# Expected: 301 or 403 (Nginx serving the volume mount — directory exists)
docker compose down
```

- [ ] **Step 5: Commit**

```bash
git add deploy/docker-stack.prod.yml deploy/docker-compose.dev.yml deploy/themes/.gitkeep deploy/langs/.gitkeep
git commit -m "feat: volume-mount themes/ and langs/ into Nginx for runtime extension loading"
```

---

## Task 14: Game validation script

**Files:**
- Create: `scripts/validate-game.sh`

- [ ] **Step 1: Create the script**

```bash
#!/bin/bash
# scripts/validate-game.sh — Verifies a community game implements the required API contract
# Usage: ./scripts/validate-game.sh <game-url>

set -euo pipefail

GAME_URL="${1:-}"
if [ -z "$GAME_URL" ]; then
  echo "Usage: $0 <game-url>"
  echo "Example: $0 http://localhost:8080"
  exit 1
fi

PASS=0
FAIL=0

check() {
  if [ "$2" = "ok" ]; then
    echo "  ✓ $1"; PASS=$((PASS + 1))
  else
    echo "  ✗ $1 — $2"; FAIL=$((FAIL + 1))
  fi
}

echo "Validating game at: $GAME_URL"
echo ""

HEALTH=$(curl -sf --max-time 5 "$GAME_URL/health" 2>/dev/null || echo "")

if echo "$HEALTH" | python3 -c "import sys,json; d=json.load(sys.stdin); exit(0 if d.get('status')=='healthy' else 1)" 2>/dev/null; then
  check "GET /health → {status: healthy}" "ok"
else
  check "GET /health → {status: healthy}" "got: $HEALTH"
fi

if echo "$HEALTH" | python3 -c "import sys,json; d=json.load(sys.stdin); exit(0 if 'game' in d else 1)" 2>/dev/null; then
  check "GET /health includes 'game' field" "ok"
else
  check "GET /health includes 'game' field" "missing 'game' key"
fi

echo ""
echo "Results: $PASS passed, $FAIL failed"
[ $FAIL -eq 0 ] && echo "Game contract validation passed." || exit 1
```

- [ ] **Step 2: Make executable**

```bash
chmod +x scripts/validate-game.sh
```

- [ ] **Step 3: Commit**

```bash
git add scripts/validate-game.sh
git commit -m "feat: add validate-game.sh — checks community game health endpoint contract"
```

---

## Task 15: event-game-games — template game

**Repository:** `event-game-games` (create this repo separately on GitHub)

- [ ] **Step 1: Create template/Dockerfile**

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app/ ./app/
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 2: Create template/requirements.txt**

```
fastapi==0.115.0
uvicorn==0.30.6
httpx==0.27.0
pydantic==2.9.0
```

- [ ] **Step 3: Create template/.env.example**

```bash
MAIN_BACKEND_URL=http://event-game-backend:8000
GAME_SLUG=my-game
SOLUTION_ANSWER=the-expected-answer
CORS_ORIGINS=https://events.example.com
```

- [ ] **Step 4: Create template/app/auth.py**

```python
# template/app/auth.py
"""Forward player cookie to main backend to authenticate."""
import os
import httpx
from fastapi import HTTPException, Request

MAIN_BACKEND_URL = os.getenv("MAIN_BACKEND_URL", "http://event-game-backend:8000")


async def get_current_user(request: Request) -> dict:
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{MAIN_BACKEND_URL}/v1/auth/me",
            cookies={"access_token": token},
            timeout=5.0,
        )
    if resp.status_code != 200:
        raise HTTPException(status_code=401, detail="Invalid session")
    return resp.json()
```

- [ ] **Step 5: Create template/app/progress.py**

```python
# template/app/progress.py
"""Report game milestone to main backend so AI hint system has context."""
import os
import httpx

MAIN_BACKEND_URL = os.getenv("MAIN_BACKEND_URL", "http://event-game-backend:8000")
GAME_SLUG = os.getenv("GAME_SLUG", "my-game")


async def report_milestone(access_token: str, milestone: str) -> None:
    async with httpx.AsyncClient() as client:
        await client.post(
            f"{MAIN_BACKEND_URL}/v1/games/{GAME_SLUG}/progress",
            cookies={"access_token": access_token},
            json={"milestone": milestone},
            timeout=5.0,
        )
```

- [ ] **Step 6: Create template/app/submit.py**

```python
# template/app/submit.py
"""Submit final answer to main backend."""
import os
import httpx

MAIN_BACKEND_URL = os.getenv("MAIN_BACKEND_URL", "http://event-game-backend:8000")
GAME_SLUG = os.getenv("GAME_SLUG", "my-game")


async def submit_answer(access_token: str, solution: str) -> dict:
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{MAIN_BACKEND_URL}/v1/games/{GAME_SLUG}/submit",
            cookies={"access_token": access_token},
            json={"solution": solution},
            timeout=5.0,
        )
    return resp.json()
```

- [ ] **Step 7: Create template/app/main.py**

```python
# template/app/main.py
"""Minimal game template — implements the full event-game API contract."""
import os
from fastapi import FastAPI, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from app.auth import get_current_user
from app.progress import report_milestone
from app.submit import submit_answer

GAME_SLUG = os.getenv("GAME_SLUG", "my-game")
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")

app = FastAPI(title=f"Game: {GAME_SLUG}")
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"status": "healthy", "game": GAME_SLUG}


@app.post("/api/game/start")
async def start_game(request: Request, user: dict = Depends(get_current_user)):
    """Report 'game_started' milestone when the player begins."""
    token = request.cookies.get("access_token", "")
    await report_milestone(token, "game_started")
    return {"message": f"Welcome, {user['username']}! Game started."}


@app.post("/api/game/submit")
async def submit(request: Request, user: dict = Depends(get_current_user)):
    """Submit the player's final answer to the main backend."""
    body = await request.json()
    token = request.cookies.get("access_token", "")
    return await submit_answer(token, body.get("solution", ""))
```

- [ ] **Step 8: Commit to event-game-games**

```bash
git add template/
git commit -m "feat: add game template implementing full API contract (health, progress, submit)"
```

---

## Task 16: event-game-themes — template and CI

**Repository:** `event-game-themes` (create separately on GitHub)

- [ ] **Step 1: Create template/theme.css**

```css
/* template/theme.css
 * Event Game Framework — Theme Template
 * Copy to themes/<your-name>/theme.css and edit.
 * All tokens below are REQUIRED. Colours use HSL without the hsl() wrapper.
 */
[data-theme="template"] {
  --primary: 220 90% 56%;
  --primary-foreground: 0 0% 100%;
  --secondary: 220 14% 46%;
  --secondary-foreground: 0 0% 100%;
  --accent: 142 76% 36%;
  --accent-foreground: 0 0% 100%;
  --background: 0 0% 100%;
  --foreground: 222 84% 5%;
  --card: 0 0% 100%;
  --card-foreground: 222 84% 5%;
  --muted: 210 40% 96%;
  --muted-foreground: 215 16% 47%;
  --border: 214 32% 91%;
  --input: 214 32% 91%;
  --ring: 220 90% 56%;
  --destructive: 0 84% 60%;
  --destructive-foreground: 0 0% 100%;
  --font-family: 'Inter', system-ui, sans-serif;
  --radius: 0.5rem;
}
```

- [ ] **Step 2: Create .github/workflows/validate.yml**

```yaml
name: Validate Themes
on: [pull_request]
jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Check required tokens
        run: |
          REQUIRED=(--primary --primary-foreground --background --foreground
                     --card --card-foreground --muted --muted-foreground
                     --border --input --ring --destructive --destructive-foreground --radius)
          FAILED=0
          for dir in */; do
            css="${dir}theme.css"
            [ -f "$css" ] || continue
            echo "Checking $css..."
            for token in "${REQUIRED[@]}"; do
              grep -q "$token" "$css" || { echo "  ✗ Missing: $token"; FAILED=1; }
            done
          done
          exit $FAILED
```

- [ ] **Step 3: Commit to event-game-themes**

```bash
git add template/ .github/
git commit -m "feat: add annotated theme template and CI required-token validation"
```

---

## Task 17: event-game-langs — template and CI

**Repository:** `event-game-langs` (create separately on GitHub)

- [ ] **Step 1: Create template.json**

```json
{
  "_comment": "Copy to langs/<locale>.json (e.g. langs/de.json). Translate values, not keys.",
  "login": {
    "usernamePlaceholder": "Username",
    "passwordPlaceholder": "Password",
    "submitButton": "Sign In",
    "loadingMessage": "Signing in..."
  },
  "nav": {
    "games": "Games",
    "leaderboard": "Leaderboard",
    "profile": "Profile",
    "notifications": "Notifications",
    "teamManagement": "Teams",
    "dashboard": "Dashboard"
  },
  "chat": {
    "inputPlaceholder": "Type a message...",
    "sendButton": "Send",
    "askAI": "Ask AI for a hint...",
    "connecting": "Connecting...",
    "rateLimitExceeded": "Rate limit exceeded. Wait {seconds}s..."
  },
  "common": {
    "loading": "Loading...",
    "error": "Error",
    "retry": "Retry",
    "submit": "Submit",
    "cancel": "Cancel",
    "save": "Save",
    "close": "Close"
  },
  "footer": {
    "roleLabel": "Role:",
    "roles": {
      "player": "You can play games and change your password.",
      "team_captain": "You can manage your team.",
      "admin": "Full system access."
    }
  }
}
```

- [ ] **Step 2: Create .github/workflows/validate.yml**

```yaml
name: Validate Language Packs
on: [pull_request]
jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Check JSON validity and required keys
        run: |
          python3 - <<'EOF'
          import json, sys, os

          def flat_keys(d, prefix=""):
              for k, v in d.items():
                  if k == "_comment": continue
                  full = f"{prefix}.{k}" if prefix else k
                  if isinstance(v, dict): flat_keys(v, full)
                  else: yield full

          template_keys = list(flat_keys(json.load(open("template.json"))))
          failed = False

          for fname in os.listdir("."):
              if not fname.endswith(".json") or fname == "template.json": continue
              print(f"Checking {fname}...")
              try:
                  data = json.load(open(fname))
              except json.JSONDecodeError as e:
                  print(f"  ✗ Invalid JSON: {e}"); failed = True; continue
              for key in template_keys:
                  parts = key.split(".")
                  v = data
                  for p in parts:
                      v = v.get(p) if isinstance(v, dict) else None
                  if v is None:
                      print(f"  ✗ Missing key: {key}"); failed = True

          sys.exit(1 if failed else 0)
          EOF
```

- [ ] **Step 3: Commit to event-game-langs**

```bash
git add template.json .github/
git commit -m "feat: add annotated lang template and CI key-completeness validation"
```

---

## Task 18: event-game-events — template and CI

**Repository:** `event-game-events` (create separately on GitHub)

- [ ] **Step 1: Create template.yml**

```yaml
# template.yml — Event Game Framework event template
# Copy, rename (e.g. halloween_2026.yml), fill in values.
# Drop into your server's events/ directory. Set is_active: true to activate.

event:
  year: 2026
  title: "Your Event Title"
  description: "One paragraph shown on the event overview."
  author: "Your Name"
  is_active: false          # Set true on the server to activate
  show_points: true
  theme: default            # Name of a folder in themes/
  language: en              # Must match a file in langs/
  ui_text:
    en:
      tagline: "Your event tagline"
    de:
      tagline: "Ihr Veranstaltungs-Slogan"

games:
  - slug: my-game                    # Unique — used in API calls and Docker service name
    title: "My Challenge"
    description: "What the player needs to accomplish."
    category: puzzle                 # puzzle | security | forensics | memory | trivia
    points: 100
    image: ghcr.io/event-game-games/slide-puzzle:1.0.0
    solution_answer: "THE ANSWER"   # Case-insensitive match
    url: https://events.example.com/games/my-game
    milestones:
      - id: step_one
        ai_context: "Player completed step one. Do not hint about it."
      - id: step_two
        ai_context: "Player completed step two. Hint about step three only."
    hints:
      - "First hint for players"
      - "Second hint for players"
    dependencies: []                 # Slugs that must be completed first

teams:
  - name: "Team Alpha"
    members:
      - username: player1
        password: changeme123
      - username: player2
        password: changeme123
```

- [ ] **Step 2: Create .github/workflows/validate.yml**

```yaml
name: Validate Events
on: [pull_request]
jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: pip install pyyaml
      - name: Validate YAML structure
        run: |
          python3 - <<'EOF'
          import yaml, sys, os

          REQUIRED_EVENT = ["year", "title", "is_active"]
          REQUIRED_GAME  = ["slug", "image", "title"]
          failed = False

          for fname in os.listdir("."):
              if not fname.endswith(".yml") or fname == "template.yml": continue
              print(f"Checking {fname}...")
              data = yaml.safe_load(open(fname))
              for f in REQUIRED_EVENT:
                  if f not in data.get("event", {}):
                      print(f"  ✗ Missing event.{f}"); failed = True
              for i, game in enumerate(data.get("games", [])):
                  for f in REQUIRED_GAME:
                      if f not in game:
                          print(f"  ✗ Game {i} missing {f}"); failed = True

          sys.exit(1 if failed else 0)
          EOF
```

- [ ] **Step 3: Commit to event-game-events**

```bash
git add template.yml .github/
git commit -m "feat: add annotated event template and CI structure validation"
```

---

## Final verification

- [ ] **Run full backend test suite:**

```bash
cd backend && pytest --cov=app --cov-report=term-missing
```

Expected: ≥ 80% coverage, all tests PASSED

- [ ] **Run full frontend test suite:**

```bash
cd frontend && npm run test:run
```

Expected: All tests PASSED

- [ ] **Run game validation against template game:**

```bash
cd event-game-games/template
docker build -t game-template .
docker run -d -p 8080:8000 --name game-template \
  -e MAIN_BACKEND_URL=http://localhost:8000 \
  -e GAME_SLUG=template \
  -e SOLUTION_ANSWER=test \
  game-template
cd ../../event-game
./scripts/validate-game.sh http://localhost:8080
docker stop game-template && docker rm game-template
```

Expected:
```
  ✓ GET /health → {status: healthy}
  ✓ GET /health includes 'game' field
Results: 2 passed, 0 failed
Game contract validation passed.
```
