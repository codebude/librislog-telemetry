"""Tests for the database module."""

import sqlite3

from sqlmodel import Session

from app.database import (
    _dispose_engine,
    _set_sqlite_pragmas,
    create_db_and_tables,
    engine,
    get_session,
)
from app.models import Installation


def test_set_sqlite_pragmas_applies_pragmas(mocker):
    cursor = mocker.Mock()
    conn = mocker.Mock(spec=sqlite3.Connection)
    conn.cursor.return_value = cursor

    _set_sqlite_pragmas(conn, None)

    executed = [call.args[0] for call in cursor.execute.call_args_list]
    assert "PRAGMA journal_mode=WAL" in executed
    assert "PRAGMA synchronous=NORMAL" in executed
    assert cursor.close.called


def test_set_sqlite_pragmas_ignores_non_sqlite():
    """Non-sqlite connections are left untouched."""
    class FakeConnection:
        pass
    conn = FakeConnection()
    _set_sqlite_pragmas(conn, None)  # should not raise


def test_create_db_and_tables_creates_installation_table():
    create_db_and_tables()
    with Session(bind=engine) as session:
        # inserting works means the table exists
        session.add(Installation(installation_id="t-db"))
        session.commit()
        assert session.get(Installation, "t-db") is not None


def test_get_session_yields_session():
    with next(get_session()) as session:
        assert isinstance(session, Session)


def test_dispose_engine_does_not_raise():
    _dispose_engine()
    _dispose_engine()  # calling twice should be safe