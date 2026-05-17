import io

from openai import AsyncOpenAI

import config
from services import proxy

_client: AsyncOpenAI | None = None


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        http_client = proxy.make_openai_http_client()
        _client = AsyncOpenAI(
            api_key=config.OPENAI_API_KEY,
            **({"http_client": http_client} if http_client else {}),
        )
    return _client


async def transcribe(file_bytes: bytes) -> str:
    client = _get_client()
    audio = io.BytesIO(file_bytes)
    audio.name = "voice.ogg"
    result = await client.audio.transcriptions.create(
        model="whisper-1",
        file=audio,
        language="ru",
    )
    return result.text
