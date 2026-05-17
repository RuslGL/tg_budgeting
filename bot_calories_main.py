import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

import config
from bot.handlers import calories, commands
from bot.middlewares.auth import AuthMiddleware
from services.proxy import make_bot_session

logging.basicConfig(level=config.LOG_LEVEL)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("aiogram.event").setLevel(logging.WARNING)


async def main() -> None:
    bot = Bot(token=config.BOT_TOKEN_CALORIES, session=make_bot_session())
    dp = Dispatcher(storage=MemoryStorage())
    dp.message.middleware(AuthMiddleware())
    dp.callback_query.middleware(AuthMiddleware())
    dp.include_router(commands.router)
    dp.include_router(calories.router)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
