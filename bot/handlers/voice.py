import logging

from aiogram import Bot, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import default_state
from aiogram.types import Message, Voice

from bot.handlers.text import process_transaction
from services import transcription

router = Router()
logger = logging.getLogger(__name__)


@router.message(StateFilter(default_state))
async def handle_voice(message: Message, bot: Bot, state: FSMContext) -> None:
    voice: Voice | None = message.voice
    if not voice:
        return

    try:
        file = await bot.get_file(voice.file_id)
        buffer = await bot.download_file(file.file_path)
        file_bytes = buffer.read()
    except Exception as e:
        logger.error("Ошибка при скачивании голосового: %s", e)
        await message.answer("Не удалось загрузить голосовое сообщение. Попробуй ещё раз.")
        return

    try:
        text = await transcription.transcribe(file_bytes)
    except Exception as e:
        logger.error("Ошибка транскрипции: %s", e)
        await message.answer("Не удалось распознать речь. Попробуй ещё раз.")
        return

    logger.info("Транскрипция: %s", text)
    await process_transaction(message, text, state)
