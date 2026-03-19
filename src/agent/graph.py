"""LangGraph definition for the analytics chatbot agent."""

from langgraph.graph import StateGraph, END

from src.agent.state import AgentState
from src.agent import nodes

# Build the graph
graph_builder = StateGraph(AgentState)

# Add nodes
graph_builder.add_node("classify_intent", nodes.classify_intent)
graph_builder.add_node("generate_sql", nodes.generate_sql)
graph_builder.add_node("validate_sql", nodes.validate_sql)
graph_builder.add_node("execute_sql", nodes.execute_sql)
graph_builder.add_node("format_response", nodes.format_response)
graph_builder.add_node("handle_csv_export", nodes.handle_csv_export)
graph_builder.add_node("handle_sql_request", nodes.handle_sql_request)

# Entry point
graph_builder.set_entry_point("classify_intent")

# Route from classify_intent based on detected intent
graph_builder.add_conditional_edges(
    "classify_intent",
    lambda state: state["intent"],
    {
        "question": "generate_sql",
        "csv": "handle_csv_export",
        "sql": "handle_sql_request",
    },
)

# Route from generate_sql: off-topic exits early, otherwise validate
graph_builder.add_conditional_edges(
    "generate_sql",
    lambda state: "done" if state.get("intent") == "off_topic" else "validate",
    {
        "done": END,
        "validate": "validate_sql",
    },
)

# Route from validate_sql: error goes to format_response, ok goes to execute
graph_builder.add_conditional_edges(
    "validate_sql",
    lambda state: "error" if state.get("error") else "ok",
    {
        "error": "format_response",
        "ok": "execute_sql",
    },
)

# Linear edges
graph_builder.add_edge("execute_sql", "format_response")
graph_builder.add_edge("format_response", END)
graph_builder.add_edge("handle_csv_export", END)
graph_builder.add_edge("handle_sql_request", END)

# Compile
agent_graph = graph_builder.compile()
