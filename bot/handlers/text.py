import logging
import time

import openai
from aiogram import Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import default_state
from aiogram.types import Message

from bot.handlers.clarification import build_categories_keyboard, _confirmed
from bot.states import Form
from services import llm, sheets

router = Router()
logger = logging.getLogger(__name__)

TIMEOUT = 300  # 5 minutes


async def process_transaction(message: Message, text: str, state: FSMContext) -> None:
    try:
        categories = sheets.get_categories()
        parsed = await llm.parse_transaction(text, categories)
    except openai.RateLimitError:
        await message.answer("На аккаунте OpenAI закончились средства. Обратись к администратору.")
        return
    except Exception as e:
        logger.error("Ошибка при парсинге: %s", e)
        await message.answer("Не удалось обработать сообщение. Попробуй ещё раз.")
        return

    amount = parsed.get("amount")
    category = parsed.get("category") or "unknown"
    date = parsed.get("date")
    missing = parsed.get("missing", [])

    amount_missing = not amount or "amount" in missing
    category_missing = category == "unknown"

    if amount_missing and category_missing:
        await message.answer(
            "Не удалось определить сумму и категорию. Опиши операцию подробнее."
        )
        return

    expires_at = time.time() + TIMEOUT

    if amount_missing:
        await state.set_state(Form.clarifying_amount)
        await state.set_data({
            "category": category,
            "date": date,
            "original_text": text,
            "attempts": 0,
            "expires_at": expires_at,
        })
        await message.answer("Не удалось определить сумму. Укажи сумму операции.")
        return

    if category_missing:
        await state.set_state(Form.clarifying_category)
        await state.set_data({
            "amount": amount,
            "date": date,
            "original_text": text,
            "attempts": 0,
            "expires_at": expires_at,
        })
        kb = build_categories_keyboard(categories)
        await message.answer(
            "Не удалось определить категорию. Уточни голосом или выбери из списка:",
            reply_markup=kb,
        )
        return

    try:
        sheets.append_transaction(date, category, amount, text)
    except Exception as e:
        logger.error("Ошибка при записи в таблицу: %s", e)
        await message.answer("Не удалось записать в таблицу. Попробуй ещё раз.")
        return

    await message.answer(_confirmed(date, amount, category))


@router.message(StateFilter(default_state))
async def handle_text(message: Message, state: FSMContext) -> None:
    text = message.text
    if not text or text.startswith("/"):
        return
    await process_transaction(message, text, state)
