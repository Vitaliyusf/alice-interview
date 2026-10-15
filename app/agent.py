"""The logic behind POST /v1/ask. Today: one model call. The agent loop goes here; the route stays as is."""

import logging

from openai import AsyncOpenAI

log = logging.getLogger("app.agent")  # every line gets the request id

SYSTEM = "You are a concise assistant. If you do not know, say so."


async def answer(client: AsyncOpenAI, model: str, question: str) -> str:
    response = await client.responses.create(model=model, instructions=SYSTEM, input=question)
    log.info("model call done status=%s", response.status)
    return response.output_text
