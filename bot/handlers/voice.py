import logging

import openai
from aiogram import Bot, F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import default_state
from aiogram.types import Message, Voice

from bot.handlers.text import process_transaction
from services import transcription

router = Router()
logger = logging.getLogger(__name__)


@router.message(StateFilter(default_state), F.voice)
async def handle_voice(message: Message, bot: Bot, state: FSMContext) -> None:
    voice: Voice | None = message.voice

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
    except openai.RateLimitError:
        await message.answer("На аккаунте OpenAI закончились средства. Обратись к администратору.")
        return
    except Exception as e:
        logger.error("Ошибка транскрипции: %s", e)
        await message.answer("Не удалось распознать речь. Попробуй ещё раз.")
        return

    logger.info("TRANSCRIPTION: user_id=%s | text=%s", message.from_user.id, text)
    await process_transaction(message, text, state)
