# Rounds Analytics Bot

A Slack AI Assistant chatbot for data analytics and business intelligence on the Rounds mobile app portfolio.

The bot converts natural language questions into SQL queries, executes them against a SQLite database, and returns formatted results — all within Slack's AI Assistant interface.

## Features

- **Natural Language to SQL** — Ask questions in plain English, get data-driven answers
- **Smart Response Formatting** — Simple text for single values, formatted tables for multi-row results
- **Follow-up Questions** — Conversation context is maintained per thread
- **CSV Export** — Say "export as csv" to download query results
- **SQL Transparency** — Say "show me the SQL" to see the query used
- **Off-topic Handling** — Politely declines non-analytics questions
- **Cost-Effective** — CSV exports and SQL requests are served from cache (zero LLM calls)
- **Observable** — Full LangSmith tracing on every LLM call and graph node

## Architecture

```
User message → classify_intent (keywords) → generate_sql (LLM) → validate_sql → execute_sql → format_response (LLM)
                                           → handle_csv_export (cache, no LLM)
                                           → handle_sql_request (cache, no LLM)
```

Built with:
- **LangGraph** for agent orchestration
- **OpenAI GPT-4o-mini** for LLM
- **Slack Bolt** with AI Assistant API
- **SQLite** for data storage
- **LangSmith** for observability

## Setup

### 1. Create a Slack App

1. Go to [api.slack.com/apps](https://api.slack.com/apps) and click **Create New App** → **From scratch**
2. Name it (e.g., "Rounds Analytics") and select your workspace

**Enable Socket Mode:**
1. Go to **Settings → Socket Mode** → Enable
2. Create an App-Level Token with `connections:write` scope → save the `xapp-` token

**Enable the AI Assistant:**
1. Go to **Features → Agents & Assistants** → Enable

**Add Bot Scopes:**
1. Go to **Features → OAuth & Permissions → Scopes → Bot Token Scopes**
2. Add: `assistant:write`, `chat:write`, `files:write`, `im:history`

**Subscribe to Events:**
1. Go to **Features → Event Subscriptions** → Enable
2. Under **Subscribe to bot events**, add:
   - `assistant_thread_started`
   - `assistant_thread_context_changed`
   - `message.im`

**Install the App:**
1. Go to **Settings → Install App** → Install to Workspace
2. Copy the **Bot User OAuth Token** (`xoxb-...`)

### 2. Set Up Environment

**Requires Python 3.10+** (uses modern type hints like `list[dict]` and `X | None` syntax).

```bash
# Clone the repo
git clone https://github.com/dime-git/slack-bot
cd slack-bot
# Create and activate a virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your tokens:
#   SLACK_BOT_TOKEN=xoxb-...
#   SLACK_APP_TOKEN=xapp-...
#   OPENAI_API_KEY=sk-...
#   LANGSMITH_API_KEY=lsv2_... (optional, for tracing)
```

### 3. Run

```bash
# Seed the database and start the bot
python -m src.app
```

The bot will:
1. Auto-create the `data/` directory and SQLite database
2. Seed ~3,600 rows of sample analytics data
3. Connect to Slack via Socket Mode

You should see this in the terminal when it's running successfully:
```
INFO: Initializing database...
INFO: Starting Rounds Analytics Bot (Socket Mode)...
⚡️ Bolt app is running!
```

On first run you'll also see `Seeded 3600 rows into app_analytics.` — subsequent runs skip seeding automatically.

### 4. Use

In Slack, click the sparkle icon (✨) in the top-right or find **Rounds Analytics** under **Apps** in the sidebar. Open a thread and start asking questions:

- "How many apps do we have?"
- "Which country generates the most revenue?"
- "Show me iOS apps sorted by installs"
- "What about Android?" _(follow-up)_
- "Export as CSV"
- "Show me the SQL you used"

## Running Tests

```bash
python -m pytest tests/ -v
```

## Project Structure

```
src/
├── app.py              # Entry point (Slack Bolt + Socket Mode)
├── config.py           # Environment configuration
├── agent/
│   ├── state.py        # LangGraph state definition
│   ├── nodes.py        # Graph node functions (intent, SQL gen, format, etc.)
│   └── graph.py        # LangGraph wiring
├── database/
│   ├── connection.py   # SQLite connection + query execution
│   ├── schema.py       # Table DDL + schema description for LLM
│   └── seed.py         # Sample data generation
└── slack/
    └── handlers.py     # Slack AI Assistant event handlers
```

## Sample Data

The seed script generates realistic data for 12 mobile apps across iOS/Android, 12 countries, and 15 months (Jan 2024 — Mar 2025). Data includes growth/decline trends, seasonal patterns, and realistic revenue/cost distributions.

## LangSmith

Set `LANGSMITH_TRACING=true` and `LANGSMITH_API_KEY` in your `.env` to enable full tracing. Every LangGraph node and LLM call is automatically traced via `langchain-openai`.

View traces at [smith.langchain.com](https://smith.langchain.com).

## Further Development

A detailed roadmap is available in [`docs/ROADMAP.md`](docs/ROADMAP.md). Key areas:

### Security Measures

- **User-level access permissions** — Map Slack user IDs to permission tiers (viewer, analyst, admin) to restrict sensitive data queries (e.g., UA cost, revenue) to authorized roles
- **SQL safety hardening** — Enforce read-only database connections at the DB level (`?mode=ro`), add query timeout limits, and implement row-count caps
- **Audit logging** — Log every query with user ID, timestamp, SQL, and result summary for compliance and debugging
- **Data privacy** — PII detection in results before sending to Slack, configurable column-level access control

### Upcoming Features

- **Data visualization** — Auto-generate charts (bar, line, trend) via matplotlib and upload as images to Slack threads when a visualization is more useful than a table
- **Scheduled reports** — Recurring queries delivered to channels on a schedule (e.g., "weekly revenue summary every Monday at 9am")
- **Proactive alerts** — Threshold-based notifications (e.g., "alert if any app's revenue drops 20%+ week-over-week") and anomaly detection on key metrics
- **Enhanced query intelligence** — Suggested follow-up questions, query templates via slash commands, and "did you mean?" disambiguation
- **Multi-source data** — Connect to multiple databases (analytics, CRM, finance) with cross-source joins and a data catalog

### Production Readiness (Prioritized)

| Priority | Improvement |
|----------|-------------|
| **P0** | Replace in-memory cache with Redis for thread state (survives restarts) |
| **P0** | Graceful error recovery for LLM timeouts, rate limits, and DB failures |
| **P0** | Read-only database connection enforced at the DB level |
| **P0** | Health check endpoint for uptime monitoring |
| **P0** | Structured JSON logging with request IDs |
| **P1** | Connection pooling via SQLAlchemy for PostgreSQL migration |
| **P1** | Per-user rate limiting to prevent LLM API abuse |
| **P1** | Prompt versioning for A/B testing and rollback |
| **P1** | Token usage tracking and cost alerts per user/query type |
| **P2** | Query result caching (Redis TTL) for identical queries |
| **P2** | Docker + docker-compose for one-command deployment |
| **P2** | CI/CD pipeline with automated tests and linting |
