import logging

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from services import llm, sheets

router = Router()
logger = logging.getLogger(__name__)


@router.message()
async def handle_text(message: Message) -> None:
    text = message.text
    if not text or text.startswith("/"):
        return

    try:
        categories = sheets.get_categories()
        parsed = await llm.parse_transaction(text, categories)
    except Exception as e:
        logger.error("Ошибка при парсинге: %s", e)
        await message.answer("Не удалось обработать сообщение. Попробуй ещё раз.")
        return

    amount = parsed.get("amount")
    category = parsed.get("category") or "unknown"
    date = parsed.get("date")
    missing = parsed.get("missing", [])

    if not amount or "amount" in missing:
        await message.answer("Не удалось определить сумму. Укажи сумму операции.")
        return

    try:
        sheets.append_transaction(date, category, amount, text)
    except Exception as e:
        logger.error("Ошибка при записи в таблицу: %s", e)
        await message.answer("Не удалось записать в таблицу. Попробуй ещё раз.")
        return

    await message.answer("Внесено.")
