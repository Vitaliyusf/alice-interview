"""Check the key and the model with one call, before the server is involved:  python -m app.check"""

import asyncio
import sys

from openai import AsyncOpenAI, OpenAIError
from pydantic import ValidationError

from app.config import get_settings


async def main() -> int:
    try:
        settings = get_settings()
    except ValidationError:
        print("FAIL  no OPENAI_API_KEY. Copy .env.example to .env and paste the key after the = sign.")
        return 1
    key = settings.openai_api_key.get_secret_value()
    model = settings.openai_model
    if not key.isascii() or key != key.strip():
        print(
            "FAIL  the key has a space or an invisible character. Paste it again, straight from the source."
        )
        return 1
    async with AsyncOpenAI(api_key=key, timeout=settings.openai_timeout_s, max_retries=1) as client:
        try:
            response = await client.responses.create(model=model, input="Reply with one word: pong")
        except OpenAIError as exc:
            print(f"FAIL  {type(exc).__name__} with model {model!r}. 401: the key. 404: the model name.")
            return 1
    print(f"OK    model={model} answer={response.output_text.strip()[:20]!r} key_length={len(key)}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
