import asyncio
import logging

import aiohttp
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from maxapi import Bot, Dispatcher
from maxapi.methods.types.getted_updates import process_update_webhook

import config

logging.basicConfig(level=logging.INFO)
logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

WEBHOOK_URL = "http://aaayyy.ru/max/webhook"
WEBHOOK_PORT = 8090

bot = Bot(config.BOT_TOKEN_MAX)
dp = Dispatcher()
app = FastAPI()


@dp.message_created()
async def on_message(event) -> None:
    try:
        sender = event.message.sender
        user_id = str(sender.user_id) if sender else "unknown"
        body = event.message.body
        text = getattr(body, "text", "") or ""
        attachments = getattr(body, "attachments", []) or []

        logger.info("Received from %s: text=%r attachments=%d", user_id, text, len(attachments))

        for att in attachments:
            logger.info("  attachment type=%r", getattr(att, "type", "?"))

        await event.message.answer("Получил сообщение!")

    except Exception as e:
        logger.error("Handler error: %s", e)


@app.post("/webhook")
async def handle_webhook(request: Request) -> JSONResponse:
    try:
        body = await request.body()
        logger.info("Webhook POST received: %s", body[:500])
        data = await request.json()
        logger.info("Webhook data: %s", str(data)[:300])
        event = await process_update_webhook(event_json=data, bot=bot)
        logger.info("Parsed event: %s", event)
        if event:
            await dp.handle(event)
    except Exception as e:
        logger.error("Webhook error: %s", e)
    return JSONResponse({"ok": True})


@app.get("/health")
async def health() -> JSONResponse:
    return JSONResponse({"ok": True})


async def register_webhook() -> None:
    async with aiohttp.ClientSession() as session:
        # clean old
        subs_resp = await session.get(
            "https://botapi.max.ru/subscriptions",
            headers={"Authorization": config.BOT_TOKEN_MAX},
        )
        for sub in (await subs_resp.json()).get("subscriptions", []):
            url = sub.get("url", "")
            if url:
                await session.delete(
                    f"https://botapi.max.ru/subscriptions?url={url}",
                    headers={"Authorization": config.BOT_TOKEN_MAX},
                )
        # register
        resp = await session.post(
            "https://botapi.max.ru/subscriptions",
            headers={"Authorization": config.BOT_TOKEN_MAX},
            json={
                "url": WEBHOOK_URL,
                "update_types": ["message_created", "bot_started"],
            },
        )
        result = await resp.json()
        if result.get("success"):
            logger.info("Webhook registered: %s", WEBHOOK_URL)
        else:
            logger.error("Webhook registration failed: %s", result)


async def main() -> None:
    # Initialize dispatcher (required for webhook mode)
    await dp._Dispatcher__ready(bot)
    await register_webhook()
    cfg = uvicorn.Config(app, host="0.0.0.0", port=WEBHOOK_PORT, log_level="warning")
    server = uvicorn.Server(cfg)
    logger.info("Max bot started on port %d", WEBHOOK_PORT)
    await server.serve()


if __name__ == "__main__":
    asyncio.run(main())
