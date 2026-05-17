import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

import config
from personal_assistant import sheets
from personal_assistant.handlers import router
from personal_assistant.scheduler import setup_scheduler
from services.proxy import make_bot_session

logging.basicConfig(level=config.LOG_LEVEL)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("aiogram.event").setLevel(logging.WARNING)
logging.getLogger("apscheduler").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


async def main() -> None:
    bot = Bot(token=config.BOT_TOKEN_ASSISTANT, session=make_bot_session())
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)

    try:
        sheets.update_headers()
        logger.info("Заголовки таблицы обновлены")
    except Exception as e:
        logger.warning("Не удалось обновить заголовки: %s", e)

    scheduler = setup_scheduler(bot)
    scheduler.start()
    logger.info("Планировщик запущен")

    try:
        await dp.start_polling(bot)
    finally:
        scheduler.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
