import io

from openai import AsyncOpenAI

import config

_client: AsyncOpenAI | None = None


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(api_key=config.OPENAI_API_KEY)
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
