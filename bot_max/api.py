import asyncio
import logging

import aiohttp

import config

logger = logging.getLogger(__name__)

BASE_URL = "https://api.icq.net/bot/v1"


class MaxBotAPI:
    def __init__(self, token: str):
        self.token = token
        self._session: aiohttp.ClientSession | None = None

    def _make_connector(self):
        if config.PROXY_URL and config.PROXY_URL.startswith("socks"):
            from aiohttp_socks import ProxyConnector
            return ProxyConnector.from_url(config.PROXY_URL)
        return None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            connector = self._make_connector()
            self._session = aiohttp.ClientSession(connector=connector)
        return self._session

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()

    async def _get(self, method: str, **params) -> dict:
        session = await self._get_session()
        url = f"{BASE_URL}/{method}"
        params["token"] = self.token
        async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=35)) as resp:
            return await resp.json()

    async def _post(self, method: str, **params) -> dict:
        session = await self._get_session()
        url = f"{BASE_URL}/{method}"
        params["token"] = self.token
        async with session.post(url, params=params, timeout=aiohttp.ClientTimeout(total=15)) as resp:
            return await resp.json()

    async def poll_events(self, last_event_id: int = 0) -> list[dict]:
        try:
            data = await self._get(
                "events/get",
                lastEventId=last_event_id,
                pollTime=25,
            )
            return data.get("events", [])
        except asyncio.TimeoutError:
            return []
        except Exception as e:
            logger.warning("Poll error: %s", e)
            await asyncio.sleep(5)
            return []

    async def send_text(self, chat_id: str, text: str) -> None:
        try:
            await self._post("messages/sendText", chatId=chat_id, text=text)
        except Exception as e:
            logger.error("Send error: %s", e)

    async def get_file_url(self, file_id: str) -> str | None:
        try:
            data = await self._get("files/getInfo", fileId=file_id)
            return data.get("fileInfo", {}).get("url")
        except Exception as e:
            logger.error("File info error: %s", e)
            return None

    async def download_file(self, url: str) -> bytes | None:
        try:
            session = await self._get_session()
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=60)) as resp:
                return await resp.read()
        except Exception as e:
            logger.error("Download error: %s", e)
            return None
