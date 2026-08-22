from __future__ import annotations

import unittest
from types import SimpleNamespace

from bot.config import GenerationParams
from bot.llm import OpenRouterClient


class FakeResponse:
    def raise_for_status(self) -> None:
        pass

    def json(self) -> dict:
        return {"choices": [{"message": {"content": "ok"}}]}


class FakeHttpClient:
    def __init__(self) -> None:
        self.payload: dict | None = None

    async def post(self, path: str, *, json: dict) -> FakeResponse:
        self.payload = json
        return FakeResponse()

    async def aclose(self) -> None:
        pass


class LlmPayloadTests(unittest.IsolatedAsyncioTestCase):
    async def test_openrouter_sampling_parameters_are_sent(self) -> None:
        settings = SimpleNamespace(
            openrouter_api_key="test",
            openrouter_default_model="cognitivecomputations/dolphin-mistral-24b-venice-edition",
        )
        llm = OpenRouterClient(settings)
        fake_client = FakeHttpClient()
        llm._client = fake_client

        params = GenerationParams(1.05, 1.0, 0, 0.5, 0.4, 1.0, 0.0, 0.0, 900)
        await llm.generate_with_params("question", params=params)

        payload = fake_client.payload
        assert payload is not None
        self.assertEqual(payload["temperature"], 1.05)
        self.assertEqual(payload["top_p"], 1.0)
        self.assertEqual(payload["top_k"], 0)
        self.assertEqual(payload["presence_penalty"], 0.5)
        self.assertEqual(payload["frequency_penalty"], 0.4)
        self.assertEqual(payload["repetition_penalty"], 1.0)
        self.assertEqual(payload["min_p"], 0.0)
        self.assertEqual(payload["top_a"], 0.0)
        self.assertEqual(payload["max_tokens"], 900)
        self.assertEqual(payload["messages"], [{"role": "user", "content": "question"}])


if __name__ == "__main__":
    unittest.main()
