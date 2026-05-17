import httpx

import config


def make_openai_http_client() -> httpx.AsyncClient | None:
    """Return httpx AsyncClient with SOCKS5 proxy, or None if no proxy configured."""
    if not config.PROXY_URL:
        return None
    transport = httpx.AsyncHTTPTransport(proxy=httpx.Proxy(config.PROXY_URL))
    return httpx.AsyncClient(
        transport=transport,
        timeout=httpx.Timeout(connect=10.0, read=120.0, write=30.0, pool=10.0),
    )


def make_bot_session():
    """Return AiohttpSession with SOCKS5 proxy if configured."""
    from aiogram.client.session.aiohttp import AiohttpSession
    if config.PROXY_URL:
        return AiohttpSession(proxy=config.PROXY_URL)
    return AiohttpSession()
