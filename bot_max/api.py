import aiohttp
import logging

logger = logging.getLogger(__name__)


async def download_file(url: str, token: str) -> bytes | None:
    """Download file from Max with Authorization header."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url,
                headers={"Authorization": token},
                timeout=aiohttp.ClientTimeout(total=60),
            ) as resp:
                return await resp.read()
    except Exception as e:
        logger.error("File download error: %s", e)
        return None
