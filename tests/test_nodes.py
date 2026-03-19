"""Tests for deterministic agent nodes (no LLM calls required)."""

import pytest

from src.agent.nodes import classify_intent, validate_sql, handle_csv_export, handle_sql_request
from src.agent.state import AgentState, QueryRecord


def _make_state(**overrides) -> AgentState:
    """Create a minimal AgentState with defaults."""
    state: AgentState = {
        "user_message": "",
        "thread_history": [],
        "conversation_messages": [],
        "intent": "",
        "sql_query": "",
        "query_result": [],
        "result_columns": [],
        "response": "",
        "csv_data": "",
        "error": "",
    }
    state.update(overrides)
    return state


# ── classify_intent tests ───────────────────────────────────────────────


class TestClassifyIntent:
    def test_csv_export(self):
        result = classify_intent(_make_state(user_message="export this as csv"))
        assert result["intent"] == "csv"

    def test_csv_download(self):
        result = classify_intent(_make_state(user_message="can I download the data?"))
        assert result["intent"] == "csv"

    def test_sql_show(self):
        result = classify_intent(_make_state(user_message="show me the SQL you used"))
        assert result["intent"] == "sql"

    def test_sql_query(self):
        result = classify_intent(_make_state(user_message="what sql statement did you use?"))
        assert result["intent"] == "sql"

    def test_normal_question(self):
        result = classify_intent(_make_state(user_message="how many apps do we have?"))
        assert result["intent"] == "question"

    def test_follow_up(self):
        result = classify_intent(_make_state(user_message="what about iOS?"))
        assert result["intent"] == "question"

    def test_case_insensitive(self):
        result = classify_intent(_make_state(user_message="EXPORT AS CSV"))
        assert result["intent"] == "csv"


# ── validate_sql tests ─────────────────────────────────────────────────


class TestValidateSQL:
    def test_valid_select(self):
        result = validate_sql(_make_state(sql_query="SELECT COUNT(*) FROM app_analytics"))
        assert result.get("error") is None or result.get("error") == ""

    def test_empty_query(self):
        result = validate_sql(_make_state(sql_query=""))
        assert "No SQL query" in result["error"]

    def test_drop_rejected(self):
        result = validate_sql(_make_state(sql_query="DROP TABLE app_analytics"))
        assert result.get("error")

    def test_delete_rejected(self):
        result = validate_sql(_make_state(sql_query="DELETE FROM app_analytics"))
        assert result.get("error")

    def test_update_rejected(self):
        result = validate_sql(_make_state(sql_query="UPDATE app_analytics SET installs = 0"))
        assert result.get("error")

    def test_insert_rejected(self):
        result = validate_sql(
            _make_state(sql_query="INSERT INTO app_analytics VALUES (1, 'test', 'iOS', '2024-01-01', 'US', 0, 0, 0, 0)")
        )
        assert result.get("error")

    def test_dangerous_keyword_in_select(self):
        """SELECT with a DROP in subquery should be caught."""
        result = validate_sql(
            _make_state(sql_query="SELECT * FROM app_analytics; DROP TABLE app_analytics")
        )
        assert result.get("error")

    def test_select_with_subquery(self):
        result = validate_sql(
            _make_state(sql_query="SELECT * FROM app_analytics WHERE installs > (SELECT AVG(installs) FROM app_analytics)")
        )
        assert not result.get("error")

    def test_non_select_rejected(self):
        result = validate_sql(_make_state(sql_query="TRUNCATE TABLE app_analytics"))
        assert result.get("error")


# ── handle_csv_export tests ─────────────────────────────────────────────


class TestHandleCSVExport:
    def test_no_history(self):
        result = handle_csv_export(_make_state(thread_history=[]))
        assert "no previous" in result["response"].lower()
        assert not result.get("csv_data")

    def test_with_history(self):
        record: QueryRecord = {
            "question": "how many apps?",
            "sql": "SELECT COUNT(*) FROM app_analytics",
            "result": [{"count": 12}],
            "result_columns": ["count"],
        }
        result = handle_csv_export(_make_state(thread_history=[record]))
        assert result.get("csv_data")
        assert "count" in result["csv_data"]
        assert "12" in result["csv_data"]

    def test_empty_result(self):
        record: QueryRecord = {
            "question": "test",
            "sql": "SELECT * FROM app_analytics WHERE 1=0",
            "result": [],
            "result_columns": ["app_name"],
        }
        result = handle_csv_export(_make_state(thread_history=[record]))
        assert "no results" in result["response"].lower()


# ── handle_sql_request tests ────────────────────────────────────────────


class TestHandleSQLRequest:
    def test_no_history(self):
        result = handle_sql_request(_make_state(thread_history=[]))
        assert "no previous" in result["response"].lower()

    def test_single_query(self):
        record: QueryRecord = {
            "question": "how many apps?",
            "sql": "SELECT COUNT(DISTINCT app_name) FROM app_analytics",
            "result": [{"count": 12}],
            "result_columns": ["count"],
        }
        result = handle_sql_request(
            _make_state(
                user_message="show me the sql",
                thread_history=[record],
            )
        )
        assert "SELECT COUNT" in result["sql_snippet"]

    def test_multiple_queries_matches_by_similarity(self):
        records = [
            QueryRecord(
                question="how many apps do we have?",
                sql="SELECT COUNT(DISTINCT app_name) FROM app_analytics",
                result=[{"count": 12}],
                result_columns=["count"],
            ),
            QueryRecord(
                question="what is the total revenue?",
                sql="SELECT SUM(in_app_revenue + ads_revenue) FROM app_analytics",
                result=[{"total": 1000000}],
                result_columns=["total"],
            ),
        ]
        result = handle_sql_request(
            _make_state(
                user_message="show me the sql you used to count the apps",
                thread_history=records,
            )
        )
        assert "COUNT(DISTINCT app_name)" in result["sql_snippet"]
