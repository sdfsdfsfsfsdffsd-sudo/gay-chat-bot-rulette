from __future__ import annotations

import hashlib
import logging
from typing import Any

import httpx

from bot.config import GenerationParams
from bot.config import Settings


logger = logging.getLogger(__name__)


class OpenRouterClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._client = httpx.AsyncClient(
            base_url="https://openrouter.ai/api/v1",
            timeout=60,
            headers={
                "Authorization": f"Bearer {settings.openrouter_api_key}",
                "HTTP-Referer": "https://localhost/telegram-chat-bot",
                "X-Title": "Telegram Chat Bot",
            },
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def generate(
        self,
        user_prompt: str,
        *,
        system_prompt: str | None = None,
        model: str | None = None,
        temperature: float = 0.8,
        top_p: float | None = None,
        top_k: int | None = None,
        presence_penalty: float | None = None,
        frequency_penalty: float | None = None,
        repetition_penalty: float | None = None,
        min_p: float | None = None,
        top_a: float | None = None,
        max_tokens: int | None = None,
        response_format: dict[str, Any] | None = None,
        require_supported_parameters: bool = False,
    ) -> str:
        messages = []
        if system_prompt is not None and system_prompt.strip():
            messages.append({"role": "system", "content": system_prompt.strip()})
        messages.append({"role": "user", "content": user_prompt.strip()})

        payload = {
            "model": model or self.settings.openrouter_default_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens if max_tokens is not None else 900,
        }
        if top_p is not None:
            payload["top_p"] = top_p
        if top_k is not None:
            payload["top_k"] = top_k
        if presence_penalty is not None:
            payload["presence_penalty"] = presence_penalty
        if frequency_penalty is not None:
            payload["frequency_penalty"] = frequency_penalty
        if repetition_penalty is not None:
            payload["repetition_penalty"] = repetition_penalty
        if min_p is not None:
            payload["min_p"] = min_p
        if top_a is not None:
            payload["top_a"] = top_a
        if response_format is not None:
            payload["response_format"] = response_format
        if require_supported_parameters:
            payload["provider"] = {"require_parameters": True}
        if hasattr(self._client, "headers"):
            self._client.headers["Authorization"] = f"Bearer {self.settings.openrouter_api_key}"
        system_hash = (
            hashlib.sha256(system_prompt.strip().encode("utf-8")).hexdigest()[:12]
            if system_prompt and system_prompt.strip()
            else "none"
        )
        logger.info(
            "OpenRouter request: model=%s system_prompt_sha256=%s system_prompt_chars=%d "
            "temperature=%s top_p=%s top_k=%s presence_penalty=%s frequency_penalty=%s "
            "repetition_penalty=%s max_tokens=%s",
            payload["model"],
            system_hash,
            len(system_prompt.strip()) if system_prompt else 0,
            payload.get("temperature"),
            payload.get("top_p"),
            payload.get("top_k"),
            payload.get("presence_penalty"),
            payload.get("frequency_penalty"),
            payload.get("repetition_penalty"),
            payload.get("max_tokens"),
        )
        response = await self._client.post("/chat/completions", json=payload)
        response.raise_for_status()
        data = response.json()
        logger.info(
            "OpenRouter response: requested_model=%s response_model=%s request_id=%s",
            payload["model"],
            data.get("model", "unknown"),
            data.get("id", "unknown"),
        )
        return data["choices"][0]["message"]["content"].strip()

    async def generate_with_params(
        self,
        user_prompt: str,
        *,
        params: GenerationParams,
        system_prompt: str | None = None,
        model: str | None = None,
        max_tokens: int | None = None,
        response_format: dict[str, Any] | None = None,
        require_supported_parameters: bool = False,
    ) -> str:
        return await self.generate(
            user_prompt,
            system_prompt=system_prompt,
            model=model,
            temperature=params.temperature,
            top_p=params.top_p,
            top_k=params.top_k,
            presence_penalty=params.presence_penalty,
            frequency_penalty=params.frequency_penalty,
            repetition_penalty=params.repetition_penalty,
            min_p=params.min_p,
            top_a=params.top_a,
            max_tokens=max_tokens if max_tokens is not None else params.max_tokens,
            response_format=response_format,
            require_supported_parameters=require_supported_parameters,
        )
