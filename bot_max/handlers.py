import logging
import time

import openai

import config
from bot_max.api import MaxBotAPI
from services import llm, sheets, transcription

logger = logging.getLogger(__name__)

TIMEOUT = 300  # 5 minutes

# In-memory state per chat_id
_states: dict[str, dict] = {}


def _get_state(chat_id: str) -> dict:
    return _states.get(chat_id, {})


def _set_state(chat_id: str, data: dict) -> None:
    _states[chat_id] = data


def _clear_state(chat_id: str) -> None:
    _states.pop(chat_id, None)


def _is_expired(state: dict) -> bool:
    return time.time() > state.get("expires_at", 0)


async def _save_transaction(api: MaxBotAPI, chat_id: str, date: str, category: str,
                             amount: float, text: str, author: str) -> None:
    try:
        sheets.append_row(date, category, "расход", amount, text, author, config.COMPANY)
        await api.send_text(chat_id, f"Записано: {category} — {amount}")
    except Exception as e:
        logger.error("Sheets error: %s", e)
        await api.send_text(chat_id, "Не удалось записать в таблицу. Попробуй ещё раз.")


async def process_transaction(api: MaxBotAPI, chat_id: str, user_id: str, text: str) -> None:
    logger.info("PROCESS: user_id=%s | text=%s", user_id, text)

    try:
        categories = sheets.get_categories()
        parsed = await llm.parse_transaction(text, categories)
    except openai.RateLimitError:
        await api.send_text(chat_id, "На аккаунте OpenAI закончились средства.")
        return
    except Exception as e:
        logger.error("Ошибка парсинга: %s", e)
        await api.send_text(chat_id, "Не удалось обработать сообщение. Попробуй ещё раз.")
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
        await api.send_text(chat_id, "Не удалось определить сумму и категорию. Опиши подробнее.")
        return

    if amount_missing:
        _set_state(chat_id, {
            "step": "clarifying_amount",
            "category": category,
            "date": date,
            "original_text": text,
            "author": author,
            "expires_at": expires_at,
        })
        await api.send_text(chat_id, "Не удалось определить сумму. Укажи сумму операции.")
        return

    if category_missing:
        cats_text = "\n".join(f"{i+1}. {c}" for i, c in enumerate(categories))
        _set_state(chat_id, {
            "step": "clarifying_category",
            "amount": amount,
            "date": date,
            "original_text": text,
            "author": author,
            "categories": categories,
            "expires_at": expires_at,
        })
        await api.send_text(
            chat_id,
            f"Не удалось определить категорию. Уточни или напиши номер:\n{cats_text}"
        )
        return

    await _save_transaction(api, chat_id, date, category, amount, text, author)


async def handle_clarification(api: MaxBotAPI, chat_id: str, user_id: str, text: str) -> bool:
    state = _get_state(chat_id)
    if not state:
        return False

    if _is_expired(state):
        _clear_state(chat_id)
        return False

    step = state.get("step")

    if step == "clarifying_amount":
        try:
            amount = float(text.strip().replace(",", "."))
        except ValueError:
            await api.send_text(chat_id, "Не понял сумму. Укажи число, например: 500")
            return True
        _clear_state(chat_id)
        await _save_transaction(
            api, chat_id,
            state["date"], state["category"], amount,
            state["original_text"], state["author"]
        )
        return True

    if step == "clarifying_category":
        categories = state.get("categories", [])
        category = None

        # Try numeric selection
        try:
            idx = int(text.strip()) - 1
            if 0 <= idx < len(categories):
                category = categories[idx]
        except ValueError:
            pass

        # Try text match
        if not category:
            text_lower = text.strip().lower()
            for c in categories:
                if text_lower in c.lower():
                    category = c
                    break

        if not category:
            # Try re-parsing with GPT
            try:
                parsed = await llm.parse_transaction(text, categories)
                cat = parsed.get("category") or "unknown"
                if cat != "unknown":
                    category = cat
            except Exception:
                pass

        if not category:
            cats_text = "\n".join(f"{i+1}. {c}" for i, c in enumerate(categories))
            await api.send_text(chat_id, f"Не понял категорию. Напиши номер или название:\n{cats_text}")
            return True

        _clear_state(chat_id)
        await _save_transaction(
            api, chat_id,
            state["date"], category, state["amount"],
            state["original_text"], state["author"]
        )
        return True

    return False


async def handle_message(api: MaxBotAPI, event: dict) -> None:
    payload = event.get("payload", {})
    chat_id = payload.get("chat", {}).get("chatId", "")
    from_info = payload.get("from", {})
    user_id = str(from_info.get("userId", ""))

    if not chat_id or not user_id:
        return

    # Auth check
    allowed = config.MAX_ALLOWED_USERS
    if user_id not in allowed:
        logger.warning("Unauthorized Max user: %s", user_id)
        return

    text = payload.get("text", "").strip()
    parts = payload.get("parts", [])

    # Voice message
    voice_part = next((p for p in parts if p.get("type") == "voice"), None)
    if voice_part:
        file_id = voice_part.get("payload", {}).get("fileId")
        if not file_id:
            await api.send_text(chat_id, "Не удалось получить голосовое сообщение.")
            return
        url = await api.get_file_url(file_id)
        if not url:
            await api.send_text(chat_id, "Не удалось загрузить голосовое сообщение.")
            return
        file_bytes = await api.download_file(url)
        if not file_bytes:
            await api.send_text(chat_id, "Не удалось скачать голосовое сообщение.")
            return
        try:
            text = await transcription.transcribe(file_bytes)
        except Exception as e:
            logger.error("Transcription error: %s", e)
            await api.send_text(chat_id, "Не удалось распознать речь. Попробуй ещё раз.")
            return
        logger.info("TRANSCRIPTION: user_id=%s | text=%s", user_id, text)

    if not text:
        return

    # Skip commands
    if text.startswith("/"):
        if text.startswith("/start") or text.startswith("/help"):
            await api.send_text(chat_id, "Отправь голосовое или текстовое сообщение с расходом.")
        return

    # Handle clarification state first
    if await handle_clarification(api, chat_id, user_id, text):
        return

    await process_transaction(api, chat_id, user_id, text)
