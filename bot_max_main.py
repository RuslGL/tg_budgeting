import asyncio
import logging

import aiohttp
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from maxapi import Bot, Dispatcher
from maxapi.methods.types.getted_updates import process_update_webhook

import config
from bot_max.handlers import setup_handlers

logging.basicConfig(level=config.LOG_LEVEL)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

WEBHOOK_URL = "https://aaayyy.ru:8443/max/webhook"
WEBHOOK_PORT = 8090

bot = Bot(config.BOT_TOKEN_MAX)
dp = Dispatcher()
setup_handlers(dp, bot)

app = FastAPI()


@app.post("/webhook")
async def handle_webhook(request: Request) -> JSONResponse:
    try:
        data = await request.json()
        event = await process_update_webhook(event_json=data, bot=bot)
        if event:
            await dp.handle(event)
    except Exception as e:
        logger.error("Webhook handler error: %s", e)
    return JSONResponse({"ok": True})


@app.get("/health")
async def health() -> JSONResponse:
    return JSONResponse({"ok": True})


async def register_webhook() -> None:
    async with aiohttp.ClientSession() as session:
        # Remove old subscriptions first
        try:
            subs_resp = await session.get(
                "https://botapi.max.ru/subscriptions",
                headers={"Authorization": config.BOT_TOKEN_MAX},
            )
            subs = (await subs_resp.json()).get("subscriptions", [])
            for sub in subs:
                url = sub.get("url", "")
                if url:
                    await session.delete(
                        f"https://botapi.max.ru/subscriptions?url={url}",
                        headers={"Authorization": config.BOT_TOKEN_MAX},
                    )
                    logger.info("Removed old webhook: %s", url)
        except Exception as e:
            logger.warning("Could not clean old subscriptions: %s", e)

        # Register new webhook
        resp = await session.post(
            "https://botapi.max.ru/subscriptions",
            headers={"Authorization": config.BOT_TOKEN_MAX},
            json={
                "url": WEBHOOK_URL,
                "update_types": [
                    "message_created",
                    "bot_started",
                    "message_callback",
                    "message_edited",
                ],
            },
        )
        result = await resp.json()
        if result.get("success"):
            logger.info("Webhook registered: %s", WEBHOOK_URL)
        else:
            logger.error("Webhook registration failed: %s", result)


async def main() -> None:
    await register_webhook()
    cfg = uvicorn.Config(app, host="0.0.0.0", port=WEBHOOK_PORT, log_level="warning")
    server = uvicorn.Server(cfg)
    logger.info("Max bot webhook server started on port %d", WEBHOOK_PORT)
    await server.serve()


if __name__ == "__main__":
    asyncio.run(main())
