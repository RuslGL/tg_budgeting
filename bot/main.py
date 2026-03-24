import asyncio
import logging

from aiogram import Bot, Dispatcher

import config
from bot.handlers import commands

logging.basicConfig(level=config.LOG_LEVEL)


async def main() -> None:
    bot = Bot(token=config.BOT_TOKEN)
    dp = Dispatcher()

    dp.include_router(commands.router)

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
