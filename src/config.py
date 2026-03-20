import os
from dotenv import load_dotenv

load_dotenv()


def _get(key: str, default: str = "") -> str:
    return os.getenv(key, default)


# These are validated at import time — they're always needed
SLACK_BOT_TOKEN = _get("SLACK_BOT_TOKEN")
SLACK_APP_TOKEN = _get("SLACK_APP_TOKEN")
OPENAI_API_KEY = _get("OPENAI_API_KEY")
DATABASE_PATH = _get("DATABASE_PATH", "data/rounds_analytics.db")


def validate_config() -> None:
    """Validate that all required env vars are set. Call at app startup."""
    missing = []
    for key in ("SLACK_BOT_TOKEN", "SLACK_APP_TOKEN", "OPENAI_API_KEY"):
        if not os.getenv(key):
            missing.append(key)
    if missing:
        raise RuntimeError(
            f"Missing required environment variables: {', '.join(missing)}"
        )
