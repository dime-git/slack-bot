# Roadmap: Rounds Analytics Bot

## Security Measures

### User-Level Access Permissions
- Map Slack user IDs to permission tiers (viewer, analyst, admin)
- Restrict sensitive data queries (e.g., UA cost) to authorized roles
- Implement per-user query rate limiting to prevent abuse
- Add audit logging: every query stored with user ID, timestamp, SQL, and results summary

### SQL Safety Hardening
- Use a read-only database connection (SQLite `?mode=ro` or a read-only PostgreSQL role)
- Add query timeout limits to prevent expensive scans from blocking the bot
- Implement row-count limits on SELECT queries to protect against accidental full-table dumps

### Data Privacy
- PII detection in query results before sending to Slack
- Configurable column-level access control (hide revenue data from non-finance users)

---

## Upcoming Features

### Data Visualization
- Generate bar charts, line charts, and trend graphs using matplotlib
- Upload as images to Slack threads alongside text responses
- Auto-detect when a visualization would be more useful than a table (e.g., time-series data)

### Scheduled Reports
- Users can schedule recurring queries: "Send me weekly revenue summary every Monday at 9am"
- Deliver reports to specific Slack channels or DMs
- Support for report templates (daily installs dashboard, weekly revenue breakdown)

### Proactive Alerts
- Set threshold-based alerts: "Notify me if any app's revenue drops 20%+ week-over-week"
- Anomaly detection on key metrics (installs, revenue, UA cost)
- Deliver alerts to a dedicated Slack channel

### Enhanced Query Intelligence
- Suggested follow-up questions after each response
- Query templates for common business questions accessible via slash commands
- "Did you mean?" disambiguation when queries are ambiguous

### Multi-Source Data
- Connect to multiple databases (analytics, CRM, finance)
- Support for joining data across sources in a single query
- Data catalog showing available tables and columns per source

---

## Production Readiness (Pre-Deployment Priorities)

### P0 — Must Have
1. **Persistent caching** — Replace in-memory dict with Redis for thread state and query cache (survives restarts)
2. **Error recovery** — Graceful handling of LLM timeouts, rate limits, and database connection failures with user-friendly messages
3. **Read-only DB connection** — Enforce at the database level, not just application code
4. **Health check endpoint** — Monitoring for bot uptime and Slack connection status
5. **Structured logging** — JSON logs with request IDs for debugging production issues

### P1 — Should Have
6. **Connection pooling** — SQLAlchemy with connection pool for PostgreSQL migration
7. **Per-user rate limiting** — Prevent individual users from overwhelming the bot or LLM API
8. **Prompt versioning** — Version control system prompts separately, enabling A/B testing and rollback
9. **Token usage tracking** — Monitor and alert on LLM costs per user/query type
10. **Input sanitization** — Additional validation layer beyond SQL keyword checking

### P2 — Nice to Have
11. **Query result caching** — Cache identical query results (Redis TTL) to avoid re-running expensive SQL
12. **Load testing** — Benchmark concurrent user handling and LLM API throughput
13. **Monitoring dashboard** — Grafana/DataDog dashboard for bot usage, latency, error rates
14. **Containerization** — Docker + docker-compose for one-command deployment
15. **CI/CD pipeline** — Automated tests, linting, and deployment on push
