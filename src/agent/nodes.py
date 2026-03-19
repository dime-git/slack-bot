"""LangGraph node functions for the analytics chatbot agent."""

import csv
import io
import re
from difflib import SequenceMatcher

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from pydantic import BaseModel, Field

from src.agent.state import AgentState
from src.database.connection import execute_query
from src.database.schema import SCHEMA_DESCRIPTION

llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

# ── Pydantic models for structured LLM output ──────────────────────────

class SQLGenerationResult(BaseModel):
    """Result of converting a natural language question to SQL."""
    is_off_topic: bool = Field(
        description="True if the question is not about app analytics data"
    )
    sql_query: str = Field(
        default="",
        description="The SQLite SELECT query to answer the question. Empty if off-topic."
    )
    explanation: str = Field(
        default="",
        description="Brief explanation of any assumptions made in interpreting the question"
    )
    off_topic_message: str = Field(
        default="",
        description="Polite decline message if the question is off-topic. Empty otherwise."
    )


class FormattedResponse(BaseModel):
    """Formatted response to send to the user."""
    response: str = Field(
        description="The formatted response text using Slack mrkdwn syntax"
    )


# ── Node functions ──────────────────────────────────────────────────────

SQL_GENERATION_PROMPT = f"""You are a SQL expert for a mobile app analytics database. Convert user questions into SQLite SELECT queries.

{SCHEMA_DESCRIPTION}

Rules:
1. Only generate SELECT statements. Never generate INSERT, UPDATE, DELETE, DROP, or any other modifying statement.
2. Use proper SQLite syntax (e.g., strftime for date functions).
3. If the user asks a follow-up question, use the conversation history to understand context.
4. If the question is not related to app analytics, mobile apps, revenue, installs, or the data in this database, set is_off_topic to true and provide a polite decline message.
5. When the user mentions "revenue" without specifying, assume they mean total revenue (in_app_revenue + ads_revenue).
6. When the user mentions "profit" or "ROI", calculate as (in_app_revenue + ads_revenue - ua_cost).
7. Country codes in the database are two-letter codes (US, UK, DE, etc.). If the user mentions a full country name, map it to the code.
8. For "popularity", use total installs as the metric.
9. Always include descriptive column aliases in your queries (e.g., AS total_revenue, AS app_count).
10. If comparing time periods, be explicit about the date ranges."""


def classify_intent(state: AgentState) -> dict:
    """Classify user intent using keyword matching. No LLM call needed."""
    msg = state["user_message"].lower().strip()

    # Check for CSV export request
    csv_patterns = ["export", "csv", "download data", "download the data",
                    "download results", "give me the file", "as a file"]
    if any(p in msg for p in csv_patterns):
        return {"intent": "csv"}

    # Check for SQL display request
    sql_patterns = ["show sql", "show me the sql", "show the sql",
                    "what sql", "which sql", "the query you used",
                    "what query", "show me the query", "see the query",
                    "sql statement", "sql you used"]
    if any(p in msg for p in sql_patterns):
        return {"intent": "sql"}

    # Default: treat as a data question (the LLM will handle off-topic detection)
    return {"intent": "question"}


def generate_sql(state: AgentState) -> dict:
    """Convert natural language question to SQL. Single LLM call handles
    question understanding, follow-up resolution, AND off-topic detection."""
    messages = [SystemMessage(content=SQL_GENERATION_PROMPT)]

    # Add conversation history for follow-up context
    for msg in state.get("conversation_messages", []):
        if msg["role"] == "user":
            messages.append(HumanMessage(content=msg["content"]))
        elif msg["role"] == "assistant":
            messages.append(AIMessage(content=msg["content"]))

    # Add current question
    messages.append(HumanMessage(content=state["user_message"]))

    structured_llm = llm.with_structured_output(SQLGenerationResult)
    result: SQLGenerationResult = structured_llm.invoke(messages)

    if result.is_off_topic:
        return {
            "intent": "off_topic",
            "response": result.off_topic_message
                or "I can only help with questions about our app portfolio analytics. Feel free to ask about app installs, revenue, costs, or performance!",
        }

    return {
        "sql_query": result.sql_query,
        "error": "",
    }


DANGEROUS_KEYWORDS = [
    "DROP", "DELETE", "UPDATE", "INSERT", "ALTER",
    "CREATE", "TRUNCATE", "REPLACE", "EXEC", "GRANT", "REVOKE",
]


def validate_sql(state: AgentState) -> dict:
    """Validate SQL is safe to execute. Pure Python, no LLM call."""
    sql = state.get("sql_query", "").strip()

    if not sql:
        return {"error": "No SQL query was generated."}

    upper_sql = sql.upper()

    if not upper_sql.startswith("SELECT"):
        return {"error": "Only SELECT queries are allowed."}

    # Check for dangerous keywords (word-boundary match to avoid false positives)
    for keyword in DANGEROUS_KEYWORDS:
        if re.search(rf"\b{keyword}\b", upper_sql):
            return {"error": f"Query contains disallowed operation: {keyword}"}

    return {}


def execute_sql(state: AgentState) -> dict:
    """Execute validated SQL against the database. No LLM call."""
    try:
        rows, columns = execute_query(state["sql_query"])
        return {
            "query_result": rows,
            "result_columns": columns,
            "error": "",
        }
    except Exception as e:
        return {"error": f"Database error: {str(e)}"}


RESPONSE_FORMAT_PROMPT = """You are a data analyst assistant in Slack. Format the query results for the user.

Rules:
1. If the result is a single value (count, sum, etc.), respond with a concise natural language sentence. Do NOT use a table.
2. If the result has multiple rows, format as a Slack table using monospace code block. Keep it clean and readable.
3. Always add a brief natural language interpretation or summary after the data.
4. If assumptions were made about the query, note them briefly.
5. If there are more than 20 rows, show only the top 20 and add a note: "_Showing top 20 results. Say 'export as csv' for the full dataset._"
6. Use Slack mrkdwn formatting: *bold*, `code`, ```code blocks```.
7. For currency values, format with $ and 2 decimal places.
8. For large numbers, use comma separators (e.g., 1,234,567).
9. Keep your response concise — no unnecessary preamble."""


def format_response(state: AgentState) -> dict:
    """Format query results for Slack display. Uses LLM for natural formatting."""
    # Handle error case — no LLM call needed
    if state.get("error"):
        return {
            "response": f"Sorry, I encountered an error: {state['error']}\n\nPlease try rephrasing your question."
        }

    result = state.get("query_result", [])
    columns = state.get("result_columns", [])

    # Empty result — no LLM call needed
    if not result:
        return {"response": "The query returned no results. Try adjusting your question."}

    # Truncate for the LLM prompt if too many rows
    display_rows = result[:20]
    truncated = len(result) > 20

    # Build a compact representation for the LLM
    result_text = f"Columns: {columns}\n"
    for row in display_rows:
        result_text += str(row) + "\n"
    if truncated:
        result_text += f"\n(Total rows: {len(result)}, showing first 20)"

    messages = [
        SystemMessage(content=RESPONSE_FORMAT_PROMPT),
        HumanMessage(
            content=f"User question: {state['user_message']}\n\nQuery results:\n{result_text}"
        ),
    ]

    structured_llm = llm.with_structured_output(FormattedResponse)
    formatted: FormattedResponse = structured_llm.invoke(messages)

    return {"response": formatted.response}


def handle_csv_export(state: AgentState) -> dict:
    """Export cached query results as CSV. No LLM call."""
    history = state.get("thread_history", [])

    if not history:
        return {
            "response": "No previous query results to export. Please ask a data question first, then request a CSV export."
        }

    # Default to the most recent query
    record = history[-1]
    rows = record["result"]
    columns = record["result_columns"]

    if not rows:
        return {"response": "The last query returned no results to export."}

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=columns)
    writer.writeheader()
    writer.writerows(rows)

    return {
        "csv_data": output.getvalue(),
        "response": f"Here's your CSV export ({len(rows)} rows).",
    }


def handle_sql_request(state: AgentState) -> dict:
    """Show the SQL query used for a previous question. No LLM call
    unless disambiguation is needed among multiple cached queries."""
    history = state.get("thread_history", [])

    if not history:
        return {
            "response": "No previous queries in this thread. Ask a data question first, then I can show you the SQL."
        }

    # Single query — just return it
    if len(history) == 1:
        sql = history[0]["sql"]
        return {"response": f"Here's the SQL query I used:\n\n```sql\n{sql}\n```"}

    # Multiple queries — try to match by string similarity
    user_msg = state["user_message"].lower()
    best_match_idx = -1
    best_score = 0.0

    for i, record in enumerate(history):
        score = SequenceMatcher(None, user_msg, record["question"].lower()).ratio()
        if score > best_score:
            best_score = score
            best_match_idx = i

    # If similarity is decent, use that match. Otherwise default to last query.
    if best_score > 0.3:
        record = history[best_match_idx]
    else:
        record = history[-1]

    question = record["question"]
    sql = record["sql"]
    return {
        "response": f"For the question: _{question}_\n\nHere's the SQL I used:\n\n```sql\n{sql}\n```"
    }
