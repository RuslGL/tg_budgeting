import logging
from datetime import datetime

from aiogram import Bot, F, Router
from aiogram.types import Message

from services import sheets, transcription

router = Router()
logger = logging.getLogger(__name__)


@router.message(F.text)
async def handle_text(message: Message) -> None:
    text = message.text
    if not text or text.startswith("/"):
        return
    await _save(message, text)


@router.message(F.voice)
async def handle_voice(message: Message, bot: Bot) -> None:
    try:
        file = await bot.get_file(message.voice.file_id)
        buffer = await bot.download_file(file.file_path)
        text = await transcription.transcribe(buffer.read())
    except Exception as e:
        logger.error("Ошибка распознавания: %s", e)
        await message.answer("Не удалось распознать голосовое сообщение. Попробуй ещё раз.")
        return
    await _save(message, text)


async def _save(message: Message, text: str) -> None:
    now = datetime.now()
    date_str = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%H:%M")
    try:
        sheets.append_timer_entry(date_str, time_str, text)
    except Exception as e:
        logger.error("Ошибка записи: %s", e)
        await message.answer("Не удалось записать. Попробуй ещё раз.")
        return
    await message.answer(f"Записано.\n{date_str} {time_str}\n{text}")
