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

import config
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


def build_projects_keyboard(projects: list[str]) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text=p, callback_data=f"proj:{p}")] for p in projects]
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def _ask_project_or_save(
    message: Message,
    state: FSMContext,
    date: str,
    category: str,
    amount: float,
    original_text: str,
    author: str,
    company: str,
    expires_at: float,
) -> None:
    if company != "business":
        try:
            sheets.append_transaction(date, category, amount, original_text, author, company, project="unknown")
        except Exception as e:
            logger.error("Ошибка записи: %s", e)
            await message.answer("Не удалось записать в таблицу. Попробуй ещё раз.")
            return
        await state.clear()
        await message.answer(_confirmed(date, amount, category))
        return

    # Corp bot — try to detect project from original text first
    projects = sheets.get_projects()
    if not projects:
        try:
            sheets.append_transaction(date, category, amount, original_text, author, company, project="unknown")
        except Exception as e:
            logger.error("Ошибка записи: %s", e)
            await message.answer("Не удалось записать в таблицу. Попробуй ещё раз.")
            return
        await state.clear()
        await message.answer(_confirmed(date, amount, category))
        return

    # Check if user already named a project in their message
    text_lower = original_text.lower()
    auto_project = next(
        (p for p in projects if p.lower() in text_lower or any(w in text_lower for w in p.lower().split())),
        None
    )
    if auto_project:
        try:
            sheets.append_transaction(date, category, amount, original_text, author, company, project=auto_project)
        except Exception as e:
            logger.error("Ошибка записи: %s", e)
            await message.answer("Не удалось записать в таблицу. Попробуй ещё раз.")
            return
        await state.clear()
        await message.answer(_confirmed(date, amount, category) + f"\nПроект: {auto_project}")
        return

    # Nothing found — ask
    await state.set_state(Form.clarifying_project)
    await state.set_data({
        "date": date,
        "category": category,
        "amount": amount,
        "original_text": original_text,
        "author": author,
        "company": company,
        "expires_at": expires_at,
    })
    default = projects[0]
    kb = build_projects_keyboard(projects)
    await message.answer(
        f"К какому проекту отнести?\nПо умолчанию: {default}",
        reply_markup=kb,
    )


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
    expires_at = data.get("expires_at", 0)
    await _ask_project_or_save(message, state, date, category, amount, original, author, company, expires_at)


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
            expires_at = data.get("expires_at", 0)
            await _ask_project_or_save(message, state, date, "unknown", amount, original, author, company, expires_at)
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
    expires_at = data.get("expires_at", 0)
    await _ask_project_or_save(message, state, date, category, amount, original, author, company, expires_at)


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
    expires_at = data.get("expires_at", 0)

    await callback.answer()
    await callback.message.edit_reply_markup(reply_markup=None)
    await _ask_project_or_save(callback.message, state, date, category, amount, data["original_text"], author, company, expires_at)


async def _save_with_project(message: Message, state: FSMContext, project: str) -> None:
    data = await state.get_data()
    if _expired(data):
        await state.clear()
        await message.answer("Время вышло. Отправь сообщение заново.")
        return
    date = data["date"]
    category = data["category"]
    amount = data["amount"]
    author = data.get("author", "")
    company = data.get("company", "")
    original_text = data.get("original_text", "")
    try:
        sheets.append_transaction(date, category, amount, original_text, author, company, project=project)
    except Exception as e:
        logger.error("Ошибка записи: %s", e)
        await state.clear()
        await message.answer("Не удалось записать в таблицу. Попробуй ещё раз.")
        return
    await state.clear()
    await message.answer(_confirmed(date, amount, category) + f"\nПроект: {project}")


@router.callback_query(Form.clarifying_project, F.data.startswith("proj:"))
async def handle_project_callback(callback: CallbackQuery, state: FSMContext) -> None:
    project = callback.data.removeprefix("proj:")
    await callback.answer()
    await callback.message.edit_reply_markup(reply_markup=None)
    await _save_with_project(callback.message, state, project)


@router.message(Form.clarifying_project)
async def handle_project_text(message: Message, state: FSMContext, bot: Bot) -> None:
    text = await _extract_text(message, bot)
    if not text:
        await message.answer("Отправь текст или голосовое с названием проекта.")
        return

    projects = sheets.get_projects()
    # Match by substring (case-insensitive)
    text_lower = text.lower()
    matched = next((p for p in projects if p.lower() in text_lower or text_lower in p.lower()), None)

    if not matched:
        if projects:
            matched = projects[0]  # fallback to default
        else:
            matched = "unknown"

    await _save_with_project(message, state, matched)
