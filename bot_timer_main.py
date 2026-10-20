import asyncio
import logging

from aiogram import Bot, Dispatcher

import config
from bot.handlers import timer
from bot.middlewares.auth import AuthMiddleware
from services.proxy import make_bot_session

logging.basicConfig(level=config.LOG_LEVEL)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("aiogram.event").setLevel(logging.WARNING)


async def main() -> None:
    bot = Bot(token=config.BOT_TOKEN, session=make_bot_session())
    dp = Dispatcher()
    dp.message.middleware(AuthMiddleware(config.ALLOWED_USERS_TIMER))
    dp.include_router(timer.router)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
