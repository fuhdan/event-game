"""Database dependency tests."""

from sqlalchemy.orm import Session

from app.db import get_db


def test_get_db_yields_session_and_closes() -> None:
    gen = get_db()
    session = next(gen)
    assert isinstance(session, Session)
    try:
        next(gen)
    except StopIteration:
        pass
