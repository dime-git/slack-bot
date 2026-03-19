"""Slack AI Assistant event handlers."""

import logging
import traceback

from slack_bolt import Assistant, BoltContext, Say, SetStatus, SetSuggestedPrompts

from src.agent.graph import agent_graph
from src.agent.state import AgentState, QueryRecord

logger = logging.getLogger(__name__)

assistant = Assistant()

# In-memory cache: thread_ts -> list of QueryRecords
# In production, this would be Redis or a database
thread_cache: dict[str, list[QueryRecord]] = {}


@assistant.thread_started
def handle_thread_started(
    say: Say,
    set_suggested_prompts: SetSuggestedPrompts,
) -> None:
    """Set up initial suggested prompts when a user opens the assistant."""
    logger.info("[ASSISTANT] thread_started event received")
    set_suggested_prompts(
        prompts=[
            {
                "title": "App Overview",
                "message": "How many apps do we have in our portfolio?",
            },
            {
                "title": "Top Revenue",
                "message": "Which app generates the most total revenue?",
            },
            {
                "title": "Country Performance",
                "message": "Which country has the highest total installs?",
            },
            {
                "title": "Platform Breakdown",
                "message": "Show me the revenue breakdown by platform.",
            },
        ]
    )


@assistant.user_message
def handle_user_message(
    payload: dict,
    say: Say,
    set_status: SetStatus,
    client,
    context: BoltContext,
) -> None:
    """Handle incoming user messages in the assistant thread."""
    logger.info(f"[ASSISTANT] user_message event received: {payload.get('text', '')[:80]}")
    try:
        channel_id = payload["channel"]
        thread_ts = payload["thread_ts"]
        user_message = payload["text"]

        set_status("Analyzing your question...")

        # Fetch conversation history from the Slack thread
        conversation_messages = _fetch_thread_messages(
            client, channel_id, thread_ts
        )

        # Get cached query history for this thread
        history = thread_cache.get(thread_ts, [])

        # Build initial state for the agent graph
        initial_state: AgentState = {
            "user_message": user_message,
            "thread_history": history,
            "conversation_messages": conversation_messages,
            "intent": "",
            "sql_query": "",
            "query_result": [],
            "result_columns": [],
            "response": "",
            "csv_data": "",
            "sql_snippet": "",
            "error": "",
        }

        set_status("Running query...")

        # Invoke the LangGraph agent
        result = agent_graph.invoke(initial_state)

        logger.info(f"[AGENT] intent={result.get('intent')} | sql={result.get('sql_query') or 'none'}")
        logger.info(f"[AGENT] sql_snippet={'YES ('+str(len(result.get('sql_snippet','')))+ ' chars)' if result.get('sql_snippet') else 'none'}")
        logger.info(f"[AGENT] csv_data={'YES' if result.get('csv_data') else 'none'}")
        logger.info(f"[AGENT] response={result.get('response', '')[:120]}")
        logger.info(f"[AGENT] error={result.get('error') or 'none'}")

        # Cache the query if a new SQL query was executed
        if result.get("sql_query") and result.get("query_result") is not None:
            thread_cache.setdefault(thread_ts, []).append(
                QueryRecord(
                    question=user_message,
                    sql=result["sql_query"],
                    result=result["query_result"],
                    result_columns=result.get("result_columns", []),
                )
            )
            logger.info(f"[CACHE] stored query #{len(thread_cache[thread_ts])} for thread {thread_ts}")

        # Handle CSV file upload
        if result.get("csv_data"):
            logger.info("[RESPONSE] uploading CSV file")
            client.files_upload_v2(
                channel=channel_id,
                thread_ts=thread_ts,
                content=result["csv_data"],
                filename="query_results.csv",
                title="Query Results Export",
                initial_comment=result.get("response", "Here's your CSV export."),
            )
            logger.info("[RESPONSE] CSV upload done")
        # Handle SQL Code Snippet upload
        elif result.get("sql_snippet"):
            logger.info(f"[RESPONSE] uploading SQL snippet: {result['sql_snippet']}")
            client.files_upload_v2(
                channel=channel_id,
                thread_ts=thread_ts,
                content=result["sql_snippet"],
                filename="query.sql",
                title="SQL Query",
                initial_comment=result.get("response", "Here's the SQL query:"),
            )
            logger.info("[RESPONSE] SQL snippet upload done")
        else:
            logger.info("[RESPONSE] sending text message")
            say(result.get("response", "I couldn't generate a response. Please try again."))

    except Exception as e:
        logger.error(f"[ERROR] {traceback.format_exc()}")
        say(f"Sorry, something went wrong: {str(e)}\n\nPlease try again.")


def _fetch_thread_messages(
    client, channel_id: str, thread_ts: str
) -> list[dict]:
    """Fetch message history from a Slack thread and map to role/content format."""
    try:
        result = client.conversations_replies(
            channel=channel_id, ts=thread_ts, limit=50
        )
        messages = []
        for msg in result.get("messages", []):
            # Skip the first message (thread parent) if it's a system message
            text = msg.get("text", "")
            if not text:
                continue

            # Bot messages -> assistant role, user messages -> user role
            if msg.get("bot_id") or msg.get("subtype") == "bot_message":
                messages.append({"role": "assistant", "content": text})
            else:
                messages.append({"role": "user", "content": text})

        # Exclude the current message (last user message) since it's passed separately
        if messages and messages[-1]["role"] == "user":
            messages = messages[:-1]

        return messages
    except Exception as e:
        logger.warning(f"Could not fetch thread messages: {e}")
        return []
