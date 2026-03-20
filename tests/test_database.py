"""Integration tests for database operations with a seeded test database."""

import os
import sqlite3
import pytest

from src.database import connection
from src.database.schema import create_tables, SCHEMA_DDL
from src.database.seed import seed_database
from src.agent.nodes import execute_sql


@pytest.fixture(autouse=True)
def test_db(tmp_path):
    """Create a temporary SQLite database, seed it, and patch the connection."""
    db_path = str(tmp_path / "test.db")
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA_DDL)
    conn.commit()

    # Patch the module-level connection
    original = connection._connection
    connection._connection = conn
    try:
        seed_database()
        yield conn
    finally:
        connection._connection = original
        conn.close()


class TestExecuteSQL:
    def test_count_apps(self):
        result = execute_sql({
            "sql_query": "SELECT COUNT(DISTINCT app_name) AS app_count FROM app_analytics"
        })
        assert not result.get("error")
        assert result["query_result"][0]["app_count"] == 12

    def test_platforms_exist(self):
        result = execute_sql({
            "sql_query": "SELECT DISTINCT platform FROM app_analytics ORDER BY platform"
        })
        assert not result.get("error")
        platforms = [row["platform"] for row in result["query_result"]]
        assert platforms == ["Android", "iOS"]

    def test_country_count(self):
        result = execute_sql({
            "sql_query": "SELECT COUNT(DISTINCT country) AS country_count FROM app_analytics"
        })
        assert not result.get("error")
        assert result["query_result"][0]["country_count"] == 12

    def test_row_count_is_3600(self):
        result = execute_sql({
            "sql_query": "SELECT COUNT(*) AS total_rows FROM app_analytics"
        })
        assert not result.get("error")
        assert result["query_result"][0]["total_rows"] == 3600

    def test_revenue_columns_present(self):
        result = execute_sql({
            "sql_query": "SELECT in_app_revenue, ads_revenue, ua_cost FROM app_analytics LIMIT 1"
        })
        assert not result.get("error")
        assert result["result_columns"] == ["in_app_revenue", "ads_revenue", "ua_cost"]
        row = result["query_result"][0]
        assert row["in_app_revenue"] >= 0
        assert row["ads_revenue"] >= 0
        assert row["ua_cost"] >= 0

    def test_invalid_sql_returns_error(self):
        result = execute_sql({
            "sql_query": "SELECT * FROM nonexistent_table"
        })
        assert "error" in result
        assert result["error"]
