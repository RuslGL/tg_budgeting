import asyncio
import logging

import config
from bot_max.api import MaxBotAPI
from bot_max.handlers import handle_message

logging.basicConfig(level=config.LOG_LEVEL)
logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


async def main() -> None:
    api = MaxBotAPI(token=config.BOT_TOKEN_MAX)
    last_event_id = 0
    logger.info("Max bot started, polling...")

    try:
        while True:
            events = await api.poll_events(last_event_id)
            for event in events:
                last_event_id = max(last_event_id, event.get("eventId", 0))
                if event.get("type") == "newMessage":
                    try:
                        await handle_message(api, event)
                    except Exception as e:
                        logger.error("Handler error: %s", e)
    finally:
        await api.close()


if __name__ == "__main__":
    asyncio.run(main())
