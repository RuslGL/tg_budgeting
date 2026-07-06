import asyncio
import logging
import ssl
import time

import aiohttp
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from maxapi import Bot, Dispatcher
from maxapi.methods.types.getted_updates import process_update_webhook
from maxapi.types.attachments.attachment import ButtonsPayload
from maxapi.types.attachments.buttons.callback_button import CallbackButton

import config
from services import llm, sheets, transcription

logging.basicConfig(level=logging.INFO)
logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

WEBHOOK_URL = "https://aaayyy.ru:8443/max/webhook"
WEBHOOK_PORT = 8090
TIMEOUT = 300
MAX_ATTEMPTS = 3
MAX_API_URL = "https://platform-api2.max.ru"

bot = Bot(config.BOT_TOKEN_MAX)
bot.api_url = MAX_API_URL
dp = Dispatcher()
app = FastAPI()

# In-memory state: (chat_id, user_id) → dict
_states: dict[tuple[int, int], dict] = {}


# --- State helpers ---

def _get_state(chat_id: int, user_id: int) -> dict:
    key = (chat_id, user_id)
    state = _states.get(key, {})
    if state and time.time() > state.get("expires_at", 0):
        _states.pop(key, None)
        return {}
    return state


def _set_state(chat_id: int, user_id: int, data: dict) -> None:
    _states[(chat_id, user_id)] = data


def _clear_state(chat_id: int, user_id: int) -> None:
    _states.pop((chat_id, user_id), None)


# --- Helpers ---

def _confirmed(date: str, amount: float, category: str) -> str:
    amount_str = f"{int(amount):,}".replace(",", " ") if float(amount) == int(amount) else str(amount)
    return f"Внесено:\n{date}\n{amount_str}\n{category}"


def _build_keyboard(categories: list[str]):
    rows = []
    for i in range(0, len(categories), 2):
        row = [CallbackButton(text=cat, payload=f"cat:{cat}") for cat in categories[i:i + 2]]
        rows.append(row)
    return ButtonsPayload(buttons=rows).pack()


async def _download_audio(url: str) -> bytes | None:
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url,
                headers={"Authorization": config.BOT_TOKEN_MAX},
                timeout=aiohttp.ClientTimeout(total=60),
            ) as resp:
                return await resp.read()
    except Exception as e:
        logger.error("Audio download error: %s", e)
        return None


async def _save(chat_id: int, user_id: int, date: str, category: str,
                amount: float, original_text: str, author: str) -> None:
    try:
        sheets.append_transaction(date, category, amount, original_text, author, config.COMPANY)
        await bot.send_message(chat_id=chat_id, text=_confirmed(date, amount, category))
    except Exception as e:
        logger.error("Sheets error: %s", e)
        await bot.send_message(chat_id=chat_id, text="Не удалось записать в таблицу. Попробуй ещё раз.")
    finally:
        _clear_state(chat_id, user_id)


# --- Core processing ---

async def _process_message(chat_id: int, user_id: int, text: str) -> None:
    author = config.MAX_USER_NAMES.get(str(user_id), "")
    expires_at = time.time() + TIMEOUT

    try:
        categories = sheets.get_categories()
        parsed = await llm.parse_transaction(text, categories)
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

    if amount_missing and category_missing:
        await bot.send_message(chat_id=chat_id, text="Не удалось определить сумму и категорию. Опиши подробнее.")
        return

    if amount_missing:
        _set_state(chat_id, user_id, {
            "step": "clarifying_amount", "category": category, "date": date,
            "original_text": text, "author": author, "attempts": 0, "expires_at": expires_at,
        })
        await bot.send_message(chat_id=chat_id, text="Не удалось определить сумму. Укажи сумму операции.")
        return

    if category_missing:
        kb = _build_keyboard(categories)
        _set_state(chat_id, user_id, {
            "step": "clarifying_category", "amount": amount, "date": date,
            "original_text": text, "author": author, "categories": categories,
            "attempts": 0, "expires_at": expires_at,
        })
        await bot.send_message(
            chat_id=chat_id,
            text="Не удалось определить категорию. Уточни или выбери из списка:",
            attachments=[kb],
        )
        return

    await _save(chat_id, user_id, date, category, amount, text, author)


async def _handle_clarification(chat_id: int, user_id: int, text: str) -> bool:
    state = _get_state(chat_id, user_id)
    if not state:
        return False

    step = state["step"]

    if step == "clarifying_amount":
        try:
            amount = float(text.strip().replace(",", "."))
        except ValueError:
            await bot.send_message(chat_id=chat_id, text="Не понял сумму. Укажи число, например: 500")
            return True
        await _save(chat_id, user_id, state["date"], state["category"],
                    amount, state["original_text"], state["author"])
        return True

    if step == "clarifying_category":
        categories = state.get("categories", [])
        category = None

        try:
            categories_list = sheets.get_categories()
            parsed = await llm.parse_transaction(text, categories_list)
            cat = parsed.get("category") or "unknown"
            if cat != "unknown":
                category = cat
        except Exception:
            pass

        if not category:
            text_lower = text.strip().lower()
            for c in categories:
                if text_lower in c.lower() or c.lower() in text_lower:
                    category = c
                    break

        if not category:
            attempts = state.get("attempts", 0) + 1
            if attempts >= MAX_ATTEMPTS:
                await _save(chat_id, user_id, state["date"], "unknown",
                            state["amount"], state["original_text"], state["author"])
                return True
            state["attempts"] = attempts
            _set_state(chat_id, user_id, state)
            kb = _build_keyboard(categories)
            await bot.send_message(
                chat_id=chat_id,
                text=f"Не распознал категорию (попытка {attempts + 1} из {MAX_ATTEMPTS}). Выбери из списка:",
                attachments=[kb],
            )
            return True

        await _save(chat_id, user_id, state["date"], category,
                    state["amount"], state["original_text"], state["author"])
        return True

    return False


# --- Handlers ---

@dp.message_created()
async def on_message(event) -> None:
    try:
        sender = event.message.sender
        user_id = sender.user_id if sender else 0
        recipient = event.message.recipient
        chat_id = recipient.chat_id or user_id

        if str(user_id) not in config.MAX_ALLOWED_USERS:
            logger.warning("Unauthorized Max user: %s", user_id)
            return

        body = event.message.body
        text = getattr(body, "text", "") or ""
        attachments = getattr(body, "attachments", []) or []

        # Voice
        audio = next((a for a in attachments if str(getattr(a, "type", "")).lower() == "audio"), None)
        if audio:
            url = getattr(getattr(audio, "payload", None), "url", None)
            file_bytes = await _download_audio(url)
            if not file_bytes:
                await bot.send_message(chat_id=chat_id, text="Не удалось скачать аудио.")
                return
            try:
                text = await transcription.transcribe(file_bytes)
                logger.info("Transcribed: %r", text)
            except Exception as e:
                logger.error("Transcription error: %s", e)
                await bot.send_message(chat_id=chat_id, text="Не удалось распознать речь.")
                return

        if not text or text.startswith("/"):
            return

        # Check timeout on existing state
        state = _get_state(chat_id, user_id)
        if state and time.time() > state.get("expires_at", 0):
            _clear_state(chat_id, user_id)
            await bot.send_message(chat_id=chat_id, text="Время вышло. Отправь сообщение заново.")
            return

        if await _handle_clarification(chat_id, user_id, text):
            return

        await _process_message(chat_id, user_id, text)

    except Exception as e:
        logger.error("Handler error: %s", e)


@dp.message_callback()
async def on_callback(event) -> None:
    try:
        user_id = event.callback.user.user_id
        chat_id = event.message.recipient.chat_id if event.message else user_id
        payload = event.callback.payload or ""

        if str(user_id) not in config.MAX_ALLOWED_USERS:
            await event.answer()
            return

        await event.answer()

        if not payload.startswith("cat:"):
            return

        category = payload.removeprefix("cat:")
        state = _get_state(chat_id, user_id)

        if not state:
            await bot.send_message(chat_id=chat_id, text="Время вышло. Отправь сообщение заново.")
            return

        if time.time() > state.get("expires_at", 0):
            _clear_state(chat_id, user_id)
            await bot.send_message(chat_id=chat_id, text="Время вышло. Отправь сообщение заново.")
            return

        await _save(chat_id, user_id, state["date"], category,
                    state["amount"], state["original_text"], state["author"])

    except Exception as e:
        logger.error("Callback error: %s", e)


# --- Webhook ---

@app.post("/webhook")
async def handle_webhook(request: Request) -> JSONResponse:
    try:
        data = await request.json()
        event = await process_update_webhook(event_json=data, bot=bot)
        if event:
            await dp.handle(event)
    except Exception as e:
        logger.error("Webhook error: %s", e)
    return JSONResponse({"ok": True})


@app.get("/health")
async def health() -> JSONResponse:
    return JSONResponse({"ok": True})


async def register_webhook() -> None:
    ssl_ctx = ssl.create_default_context()
    ssl_ctx.check_hostname = False
    ssl_ctx.verify_mode = ssl.CERT_NONE
    connector = aiohttp.TCPConnector(ssl=ssl_ctx)
    async with aiohttp.ClientSession(connector=connector) as session:
        subs_resp = await session.get(
            "https://platform-api2.max.ru/subscriptions",
            headers={"Authorization": config.BOT_TOKEN_MAX},
        )
        for sub in (await subs_resp.json()).get("subscriptions", []):
            url = sub.get("url", "")
            if url:
                await session.delete(
                    f"https://platform-api2.max.ru/subscriptions?url={url}",
                    headers={"Authorization": config.BOT_TOKEN_MAX},
                )
        resp = await session.post(
            "https://platform-api2.max.ru/subscriptions",
            headers={"Authorization": config.BOT_TOKEN_MAX},
            json={
                "url": WEBHOOK_URL,
                "update_types": ["message_created", "bot_started", "message_callback"],
            },
        )
        result = await resp.json()
        if result.get("success"):
            logger.info("Webhook registered: %s", WEBHOOK_URL)
        else:
            logger.error("Webhook registration failed: %s", result)


async def main() -> None:
    ssl_ctx = ssl.create_default_context()
    ssl_ctx.check_hostname = False
    ssl_ctx.verify_mode = ssl.CERT_NONE
    bot.session = aiohttp.ClientSession(
        base_url=bot.api_url,
        timeout=bot.default_connection.timeout,
        headers={"Authorization": config.BOT_TOKEN_MAX},
        connector=aiohttp.TCPConnector(ssl=ssl_ctx),
    )
    await dp._Dispatcher__ready(bot)
    await register_webhook()
    cfg = uvicorn.Config(app, host="0.0.0.0", port=WEBHOOK_PORT, log_level="warning")
    server = uvicorn.Server(cfg)
    logger.info("Max bot started on port %d", WEBHOOK_PORT)
    await server.serve()


if __name__ == "__main__":
    asyncio.run(main())
