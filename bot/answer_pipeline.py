from __future__ import annotations

import re

from bot.config import GenerationParams
from bot.llm import OpenRouterClient


VILLAGE_SPEAKERS = ("Village", "Colin", "Maya", "Jimmy", "Michael", "Johnson", "Khan")
_SPEAKER_PATTERN = "|".join(re.escape(name) for name in VILLAGE_SPEAKERS)
_ROLEPLAY_LABEL_RE = re.compile(
    rf"(?i)(?<![\w@])(?:[*_]{{1,2}})?(?:{_SPEAKER_PATTERN})(?:[*_]{{1,2}})?"
    rf"(?:\s*\([^\n)]*\))?\s*:",
)

class AnswerExtractionError(RuntimeError):
    pass


def extract_valid_final_answer(raw: str) -> str:
    answer = raw.strip()
    if not answer:
        raise AnswerExtractionError("Model returned an empty answer")
    answer = answer.strip()
    if _ROLEPLAY_LABEL_RE.search(answer):
        raise AnswerExtractionError("Final answer still contains roleplay dialogue")
    return answer


async def generate_clean_answer(
    llm: OpenRouterClient,
    user_prompt: str,
    *,
    system_prompt: str | None = None,
    model: str,
    params: GenerationParams,
) -> str:
    raw = await llm.generate_with_params(
        user_prompt,
        system_prompt=system_prompt,
        model=model,
        params=params,
    )
    return extract_valid_final_answer(raw)
