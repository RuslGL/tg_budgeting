import logging
import time

import openai

import config
from bot_max.api import download_file
from services import llm, sheets, transcription

logger = logging.getLogger(__name__)

TIMEOUT = 300

# Per-chat clarification state
_states: dict[str, dict] = {}


def _get_state(chat_id: str) -> dict:
    return _states.get(chat_id, {})


def _set_state(chat_id: str, data: dict) -> None:
    _states[chat_id] = data


def _clear_state(chat_id: str) -> None:
    _states.pop(chat_id, None)


async def _save(bot, chat_id: str, date: str, category: str,
                amount: float, text: str, author: str) -> None:
    try:
        sheets.append_row(date, category, "расход", amount, text, author, config.COMPANY)
        await bot.send_message(chat_id=chat_id, text=f"Записано: {category} — {amount}")
    except Exception as e:
        logger.error("Sheets error: %s", e)
        await bot.send_message(chat_id=chat_id, text="Не удалось записать в таблицу. Попробуй ещё раз.")


async def process_text(bot, chat_id: str, user_id: str, text: str) -> None:
    logger.info("PROCESS max: user=%s text=%s", user_id, text)
    try:
        categories = sheets.get_categories()
        parsed = await llm.parse_transaction(text, categories)
    except openai.RateLimitError:
        await bot.send_message(chat_id=chat_id, text="На аккаунте OpenAI закончились средства.")
        return
    except Exception as e:
        logger.error("Parse error: %s", e)
        await bot.send_message(chat_id=chat_id, text="Не удалось обработать. Попробуй ещё раз.")
        return

    amount = parsed.get("amount")
    category = parsed.get("category") or "unknown"
    date = parsed.get("date")
    missing = parsed.get("missing", [])
    amount_missing = not amount or "amount" in missing
    category_missing = category == "unknown"
    author = config.MAX_USER_NAMES.get(user_id, "")
    expires_at = time.time() + TIMEOUT

    if amount_missing and category_missing:
        await bot.send_message(chat_id=chat_id, text="Не удалось определить сумму и категорию. Опиши подробнее.")
        return

    if amount_missing:
        _set_state(chat_id, {
            "step": "amount", "category": category, "date": date,
            "original_text": text, "author": author, "expires_at": expires_at,
        })
        await bot.send_message(chat_id=chat_id, text="Не удалось определить сумму. Укажи сумму операции.")
        return

    if category_missing:
        cats = "\n".join(f"{i+1}. {c}" for i, c in enumerate(categories))
        _set_state(chat_id, {
            "step": "category", "amount": amount, "date": date,
            "original_text": text, "author": author,
            "categories": categories, "expires_at": expires_at,
        })
        await bot.send_message(chat_id=chat_id, text=f"Не удалось определить категорию. Выбери номер:\n{cats}")
        return

    await _save(bot, chat_id, date, category, amount, text, author)


async def handle_clarification(bot, chat_id: str, text: str) -> bool:
    state = _get_state(chat_id)
    if not state:
        return False
    if time.time() > state.get("expires_at", 0):
        _clear_state(chat_id)
        return False

    step = state["step"]

    if step == "amount":
        try:
            amount = float(text.strip().replace(",", "."))
        except ValueError:
            await bot.send_message(chat_id=chat_id, text="Не понял сумму. Укажи число, например: 500")
            return True
        _clear_state(chat_id)
        await _save(bot, chat_id, state["date"], state["category"],
                    amount, state["original_text"], state["author"])
        return True

    if step == "category":
        categories = state.get("categories", [])
        category = None
        try:
            idx = int(text.strip()) - 1
            if 0 <= idx < len(categories):
                category = categories[idx]
        except ValueError:
            text_lower = text.strip().lower()
            for c in categories:
                if text_lower in c.lower():
                    category = c
                    break
        if not category:
            try:
                parsed = await llm.parse_transaction(text, categories)
                cat = parsed.get("category") or "unknown"
                if cat != "unknown":
                    category = cat
            except Exception:
                pass
        if not category:
            cats = "\n".join(f"{i+1}. {c}" for i, c in enumerate(categories))
            await bot.send_message(chat_id=chat_id, text=f"Не понял категорию. Напиши номер:\n{cats}")
            return True
        _clear_state(chat_id)
        await _save(bot, chat_id, state["date"], category,
                    state["amount"], state["original_text"], state["author"])
        return True

    return False


def setup_handlers(dp, bot) -> None:
    @dp.message_created()
    async def on_message(event) -> None:
        try:
            sender = event.message.sender
            user_id = str(sender.user_id) if sender else ""
            recipient = event.message.recipient
            chat_id = str(recipient.chat_id) if recipient else user_id

            if not user_id:
                return

            # Auth
            if user_id not in config.MAX_ALLOWED_USERS:
                logger.warning("Unauthorized Max user: %s", user_id)
                return

            text = ""
            body = event.message.body

            # Check for audio/voice attachment
            attachments = getattr(body, "attachments", None) or []
            audio = next((a for a in attachments if getattr(a, "type", "") in ("audio", "voice")), None)

            if audio:
                url = getattr(getattr(audio, "payload", None), "url", None)
                if not url:
                    await bot.send_message(chat_id=chat_id, text="Не удалось получить файл.")
                    return
                file_bytes = await download_file(url, config.BOT_TOKEN_MAX)
                if not file_bytes:
                    await bot.send_message(chat_id=chat_id, text="Не удалось скачать файл.")
                    return
                try:
                    text = await transcription.transcribe(file_bytes)
                    logger.info("TRANSCRIPTION max: user=%s text=%s", user_id, text)
                except Exception as e:
                    logger.error("Transcription error: %s", e)
                    await bot.send_message(chat_id=chat_id, text="Не удалось распознать речь.")
                    return
            else:
                text = (getattr(body, "text", "") or "").strip()

            if not text or text.startswith("/"):
                if text.startswith("/start") or text.startswith("/help"):
                    await bot.send_message(
                        chat_id=chat_id,
                        text="Отправь голосовое или текстовое сообщение с расходом."
                    )
                return

            if await handle_clarification(bot, chat_id, text):
                return

            await process_text(bot, chat_id, user_id, text)

        except Exception as e:
            logger.error("Handler error: %s", e)
