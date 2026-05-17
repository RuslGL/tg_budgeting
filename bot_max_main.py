import asyncio
import logging

from maxapi import Bot, Dispatcher

import config
from bot_max.handlers import setup_handlers

logging.basicConfig(level=config.LOG_LEVEL)
logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


async def main() -> None:
    bot = Bot(config.BOT_TOKEN_MAX)
    dp = Dispatcher()
    setup_handlers(dp, bot)
    logger.info("Max bot started, polling...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
