import sqlite3
from src.config import DATABASE_PATH

_connection: sqlite3.Connection | None = None


def get_connection() -> sqlite3.Connection:
    global _connection
    if _connection is None:
        _connection = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        _connection.row_factory = sqlite3.Row
    return _connection


def execute_query(sql: str) -> tuple[list[dict], list[str]]:
    """Execute a read-only SQL query. Returns (rows, column_names)."""
    stripped = sql.strip()
    if not stripped.upper().startswith("SELECT"):
        raise ValueError("Only SELECT queries are allowed.")

    conn = get_connection()
    cursor = conn.execute(stripped)
    columns = [desc[0] for desc in cursor.description]
    rows = [dict(row) for row in cursor.fetchall()]
    return rows, columns
