"""Read-only database access for the GenAI tools.

The LLM never writes SQL. Tools call fixed, parameterised queries through
``run_query``. The engine comes from ``warehouse.db_connection.get_engine`` in
production and can be replaced with ``set_engine`` (used by the tests).
"""

import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import text

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

_engine = None


def set_engine(engine) -> None:
    """Override the engine (tests)."""
    global _engine
    _engine = engine


def get_db_engine():
    global _engine
    if _engine is None:
        from warehouse.db_connection import get_engine  # imported lazily (needs pyodbc)

        _engine = get_engine()
    return _engine


def run_query(sql: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Run one read-only SELECT and return rows as dicts."""
    if not sql.lstrip().upper().startswith(("SELECT", "WITH")):
        raise ValueError("Only SELECT statements are allowed")
    with get_db_engine().connect() as conn:
        result = conn.execute(text(sql), params or {})
        return [dict(row._mapping) for row in result]


def to_datetime(value) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.replace(tzinfo=None)
    return datetime.fromisoformat(str(value).replace("T", " ").replace("Z", "")).replace(tzinfo=None)


def to_iso(value) -> str | None:
    dt = to_datetime(value)
    return dt.strftime("%Y-%m-%dT%H:%M:%S") if dt else None


def to_param(dt: datetime) -> str:
    """ISO text accepted by SQL Server (datetime2) and SQLite alike."""
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def hours_before(value, hours: float) -> str:
    return to_param(to_datetime(value) - timedelta(hours=hours))
