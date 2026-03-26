"""Async LLM client for generating chat responses in delegation experiments."""
from __future__ import annotations

import logging

from openai import AsyncOpenAI

from config import get_settings

logger = logging.getLogger(__name__)

_client: AsyncOpenAI | None = None


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        settings = get_settings()
        if not settings.llm.api_key:
            raise ValueError("LLM__API_KEY not set in configuration")
        _client = AsyncOpenAI(
            api_key=settings.llm.api_key,
            base_url=settings.llm.base_url,
        )
    return _client


async def get_chat_response(messages: list[dict], task_question: str, task_instructions: str) -> str:
    """Get a chat response from the configured LLM provider given task context."""
    client = _get_client()
    settings = get_settings()

    system_message = (
        f"You are a helpful AI assistant helping a user answer a question.\n\n"
        f"Task Instructions: {task_instructions}\n\n"
        f"Question: {task_question}\n\n"
        f"Help the user work through this question. Be concise and helpful."
    )

    api_messages = [{"role": "system", "content": system_message}]
    for msg in messages:
        api_messages.append({"role": msg["role"], "content": msg["content"]})

    logger.debug("Sending chat request with %d messages", len(api_messages))
    response = await client.chat.completions.create(
        model=settings.llm.model,
        messages=api_messages,
        max_completion_tokens=4096,
    )

    return response.choices[0].message.content or ""
