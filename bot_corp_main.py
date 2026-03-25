import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

import config
from bot.handlers import clarification, commands, text, voice
from bot.middlewares.auth import AuthMiddleware

logging.basicConfig(level=config.LOG_LEVEL)


async def main() -> None:
    bot = Bot(token=config.BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())
    dp.message.middleware(AuthMiddleware())
    dp.include_router(clarification.router)
    dp.include_router(commands.router)
    dp.include_router(voice.router)
    dp.include_router(text.router)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
