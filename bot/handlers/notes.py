import logging
from datetime import date

import openai
from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import default_state
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

import config
from bot.states import NoteForm
from services import llm, sheets, transcription

logger = logging.getLogger(__name__)

router = Router()


def _category_keyboard(categories: list[str]) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text=cat, callback_data=f"note_cat:{cat}")]
        for cat in sorted(categories)
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def _is_calendar_category(category: str) -> bool:
    return category in config.CALENDAR_CATEGORIES and bool(config.GOOGLE_CALENDAR_ID)


def _confirm_text(note_date: str, category: str, text: str, event_date: str | None) -> str:
    msg = f"Записано.\n{note_date} · {category}"
    if event_date:
        msg += f"\nСобытие: {event_date}"
    msg += f"\n\n{text}"
    return msg


async def process_note(message: Message, text: str, state: FSMContext) -> None:
    categories = sheets.get_note_categories()

    try:
        parsed = await llm.parse_note(text, categories)
    except Exception as e:
        logger.error("Ошибка LLM при разборе заметки: %s", e)
        await message.answer("Не удалось обработать заметку. Попробуй ещё раз.")
        return

    category = parsed.get("category", "unknown")
    event_date = parsed.get("event_date")
    note_date = date.today().isoformat()
    logger.info("parse_note result: category=%s event_date=%s", category, event_date)

    if category != "unknown" and category in categories:
        if _is_calendar_category(category) and not event_date:
            await state.set_state(NoteForm.clarifying_date)
            await state.update_data(text=text, date=note_date, category=category)
            await message.answer("Укажи дату события (например: 15 апреля или 2026-04-15)")
            return
        sheets.append_note(note_date, text, category, event_date)
        await message.answer(_confirm_text(note_date, category, text, event_date))
        return

    await state.set_state(NoteForm.clarifying_category)
    await state.update_data(text=text, date=note_date, event_date=event_date)
    await message.answer(
        "Какой тип заметки?",
        reply_markup=_category_keyboard(categories),
    )


@router.message(StateFilter(default_state), F.text)
async def handle_note_text(message: Message, state: FSMContext) -> None:
    logger.info("Note text from user %s: %s", message.from_user.id, message.text)
    await process_note(message, message.text, state)


@router.message(StateFilter(default_state), F.voice)
async def handle_note_voice(message: Message, bot: Bot, state: FSMContext) -> None:
    try:
        file = await bot.get_file(message.voice.file_id)
        buffer = await bot.download_file(file.file_path)
        file_bytes = buffer.read()
    except Exception as e:
        logger.error("Ошибка при скачивании голосового: %s", e)
        await message.answer("Не удалось загрузить голосовое сообщение. Попробуй ещё раз.")
        return

    try:
        text = await transcription.transcribe(file_bytes)
    except openai.RateLimitError:
        await message.answer("На аккаунте OpenAI закончились средства. Обратись к администратору.")
        return
    except Exception as e:
        logger.error("Ошибка транскрипции: %s", e)
        await message.answer("Не удалось распознать речь. Попробуй ещё раз.")
        return

    logger.info("Note voice from user %s: %s", message.from_user.id, text)
    await process_note(message, text, state)


@router.callback_query(NoteForm.clarifying_category, F.data.startswith("note_cat:"))
async def handle_category_choice(callback: CallbackQuery, state: FSMContext) -> None:
    try:
        await callback.answer()
    except TelegramBadRequest:
        return
    category = callback.data.split(":", 1)[1]
    data = await state.get_data()
    note_date = data.get("date")
    text = data.get("text")
    event_date = data.get("event_date")

    if _is_calendar_category(category) and not event_date:
        await state.set_state(NoteForm.clarifying_date)
        await state.update_data(category=category)
        await callback.message.edit_text("Укажи дату события (например: 15 апреля или 2026-04-15)")
        return

    await state.clear()
    sheets.append_note(note_date, text, category, event_date)
    await callback.message.edit_text(_confirm_text(note_date, category, text, event_date))


@router.message(NoteForm.clarifying_date, F.text)
async def handle_date_input(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    text = data.get("text")
    note_date = data.get("date")
    category = data.get("category")

    try:
        parsed = await llm.parse_note(message.text, [])
        event_date = parsed.get("event_date")
    except Exception:
        event_date = None

    if not event_date:
        await message.answer("Не удалось распознать дату. Попробуй ещё раз (например: 15 апреля или 2026-04-15)")
        return

    await state.clear()
    sheets.append_note(note_date, text, category, event_date)
    await message.answer(_confirm_text(note_date, category, text, event_date))
