import logging
import time

import openai
from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from bot.states import Form
from services import llm, sheets, transcription

router = Router()
logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 3
TIMEOUT = 300  # 5 minutes


def _expired(data: dict) -> bool:
    return time.time() > data.get("expires_at", 0)


def build_categories_keyboard(categories: list[str]) -> InlineKeyboardMarkup:
    rows = []
    for i in range(0, len(categories), 2):
        row = [
            InlineKeyboardButton(text=cat, callback_data=f"cat:{cat}")
            for cat in categories[i : i + 2]
        ]
        rows.append(row)
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _confirmed(date: str, amount: float, category: str) -> str:
    amount_str = f"{int(amount):,}".replace(",", " ") if float(amount) == int(amount) else str(amount)
    return f"Внесено:\n{date}\n{amount_str}\n{category}"


async def _extract_text(message: Message, bot: Bot) -> str | None:
    if message.text:
        return message.text
    if message.voice:
        try:
            file = await bot.get_file(message.voice.file_id)
            buffer = await bot.download_file(file.file_path)
            return await transcription.transcribe(buffer.read())
        except openai.RateLimitError:
            raise
        except Exception as e:
            logger.error("Ошибка транскрипции в уточнении: %s", e)
    return None


@router.message(Form.clarifying_amount)
async def handle_clarify_amount(message: Message, state: FSMContext, bot: Bot) -> None:
    data = await state.get_data()

    if _expired(data):
        await state.clear()
        await message.answer("Время вышло. Отправь сообщение заново.")
        return

    try:
        text = await _extract_text(message, bot)
    except openai.RateLimitError:
        await state.clear()
        await message.answer("На аккаунте OpenAI закончились средства. Обратись к администратору.")
        return
    if not text:
        await message.answer("Отправь текст или голосовое с суммой.")
        return

    try:
        categories = sheets.get_categories()
        parsed = await llm.parse_transaction(text, categories)
    except openai.RateLimitError:
        await state.clear()
        await message.answer("На аккаунте OpenAI закончились средства. Обратись к администратору.")
        return

    amount = parsed.get("amount")
    new_category = parsed.get("category")

    if not amount:
        attempts = data.get("attempts", 0) + 1
        if attempts >= MAX_ATTEMPTS:
            await state.clear()
            await message.answer("Не удалось определить сумму. Отправь сообщение заново.")
            return
        await state.update_data(attempts=attempts)
        await message.answer(
            f"Не понял сумму. Укажи число, например: 3000 "
            f"(попытка {attempts + 1} из {MAX_ATTEMPTS})."
        )
        return

    # If user provided a full new message with both amount and category — use new data entirely
    if new_category and new_category != "unknown":
        date = parsed.get("date") or data["date"]
        category = new_category
        original = text
    else:
        date = data["date"]
        category = data["category"]
        original = data["original_text"]

    author = data.get("author", "")
    company = data.get("company", "")
    try:
        sheets.append_transaction(date, category, amount, original, author, company)
    except Exception as e:
        logger.error("Ошибка записи: %s", e)
        await state.clear()
        await message.answer("Не удалось записать в таблицу. Попробуй ещё раз.")
        return

    await state.clear()
    await message.answer(_confirmed(date, amount, category))


@router.message(Form.clarifying_category)
async def handle_clarify_category(message: Message, state: FSMContext, bot: Bot) -> None:
    data = await state.get_data()

    if _expired(data):
        await state.clear()
        await message.answer("Время вышло. Отправь сообщение заново.")
        return

    try:
        text = await _extract_text(message, bot)
    except openai.RateLimitError:
        await state.clear()
        await message.answer("На аккаунте OpenAI закончились средства. Обратись к администратору.")
        return
    if not text:
        await message.answer("Отправь текст или голосовое с категорией.")
        return

    categories = sheets.get_categories()
    try:
        parsed = await llm.parse_transaction(text, categories)
    except openai.RateLimitError:
        await state.clear()
        await message.answer("На аккаунте OpenAI закончились средства. Обратись к администратору.")
        return

    category = parsed.get("category")
    new_amount = parsed.get("amount")

    if not category or category == "unknown":
        attempts = data.get("attempts", 0) + 1
        if attempts >= MAX_ATTEMPTS:
            date = data["date"]
            amount = data["amount"]
            original = data["original_text"]
            author = data.get("author", "")
            company = data.get("company", "")
            try:
                sheets.append_transaction(date, "unknown", amount, original, author, company)
            except Exception as e:
                logger.error("Ошибка записи: %s", e)
                await state.clear()
                await message.answer("Не удалось записать в таблицу. Попробуй ещё раз.")
                return
            await state.clear()
            await message.answer(_confirmed(date, amount, "unknown"))
            return
        await state.update_data(attempts=attempts)
        kb = build_categories_keyboard(categories)
        await message.answer(
            f"Не распознал категорию (попытка {attempts + 1} из {MAX_ATTEMPTS}). "
            f"Уточни голосом или выбери из списка:",
            reply_markup=kb,
        )
        return

    # If user provided a full new message with both category and amount — use new data entirely
    if new_amount:
        date = parsed.get("date") or data["date"]
        amount = new_amount
        original = text
    else:
        date = data["date"]
        amount = data["amount"]
        original = data["original_text"]

    author = data.get("author", "")
    company = data.get("company", "")
    try:
        sheets.append_transaction(date, category, amount, original, author, company)
    except Exception as e:
        logger.error("Ошибка записи: %s", e)
        await state.clear()
        await message.answer("Не удалось записать в таблицу. Попробуй ещё раз.")
        return

    await state.clear()
    await message.answer(_confirmed(date, amount, category))


@router.callback_query(Form.clarifying_category, F.data.startswith("cat:"))
async def handle_category_callback(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()

    if _expired(data):
        await state.clear()
        await callback.message.answer("Время вышло. Отправь сообщение заново.")
        await callback.answer()
        return

    category = callback.data.removeprefix("cat:")
    date = data["date"]
    amount = data["amount"]
    author = data.get("author", "")
    company = data.get("company", "")

    try:
        sheets.append_transaction(date, category, amount, data["original_text"], author, company)
    except Exception as e:
        logger.error("Ошибка записи: %s", e)
        await state.clear()
        await callback.message.answer("Не удалось записать в таблицу. Попробуй ещё раз.")
        await callback.answer()
        return

    await state.clear()
    await callback.message.answer(_confirmed(date, amount, category))
    await callback.answer()
