"""Entry point for the Rounds Analytics Slack Bot."""

import logging

from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

from src.config import SLACK_BOT_TOKEN, SLACK_APP_TOKEN, validate_config
from src.database.schema import create_tables
from src.database.seed import seed_database
from src.slack.handlers import assistant

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)

app = App(token=SLACK_BOT_TOKEN)
app.use(assistant)


def main() -> None:
    validate_config()
    logger.info("Initializing database...")
    create_tables()
    seed_database()

    logger.info("Starting Rounds Analytics Bot (Socket Mode)...")
    handler = SocketModeHandler(app, SLACK_APP_TOKEN)
    handler.start()


if __name__ == "__main__":
    main()
