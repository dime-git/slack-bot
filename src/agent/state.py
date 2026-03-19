from typing import TypedDict


class QueryRecord(TypedDict):
    question: str
    sql: str
    result: list[dict]
    result_columns: list[str]


class AgentState(TypedDict):
    user_message: str
    thread_history: list[QueryRecord]  # all cached queries for this thread
    conversation_messages: list[dict]  # [{role, content}] from Slack thread
    intent: str  # "question" | "csv" | "sql" | "off_topic"
    sql_query: str
    query_result: list[dict]
    result_columns: list[str]
    response: str
    csv_data: str  # prepared CSV string for file upload
    error: str
