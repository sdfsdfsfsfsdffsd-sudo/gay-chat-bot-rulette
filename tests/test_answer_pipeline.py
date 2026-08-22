from __future__ import annotations

import unittest

from bot.answer_pipeline import (
    AnswerExtractionError,
    extract_valid_final_answer,
    generate_clean_answer,
)
from bot.config import GenerationParams
from bot.handlers import build_answer_prompt, clean_question_text, command_argument, format_roast_target


ANSWER_MODEL = "cognitivecomputations/dolphin-mistral-24b-venice-edition"


class FakeLlm:
    def __init__(self, first: str) -> None:
        self.first = first
        self.calls: list[tuple[str, dict]] = []

    async def generate_with_params(self, prompt: str, **kwargs) -> str:
        self.calls.append((prompt, kwargs))
        return self.first


class AnswerPipelineTests(unittest.TestCase):
    def test_returns_plain_text_answer(self) -> None:
        self.assertEqual(extract_valid_final_answer("Direct answer."), "Direct answer.")

    def test_rejects_empty_answer(self) -> None:
        with self.assertRaises(AnswerExtractionError):
            extract_valid_final_answer("   ")

    def test_rejects_full_roleplay_transcript(self) -> None:
        transcript = (
            "Khan: Does anyone know the answer?\n"
            "Colin: Not my field.\n"
            "Khan (to village): Final answer."
        )
        with self.assertRaises(AnswerExtractionError):
            extract_valid_final_answer(transcript)

    def test_rejects_markdown_speaker_label(self) -> None:
        with self.assertRaises(AnswerExtractionError):
            extract_valid_final_answer("**Johnson:** Final answer.")

    def test_question_cleanup_only_removes_bot_mention(self) -> None:
        text = "@my_bot How are you?"
        self.assertEqual(clean_question_text(text, "my_bot"), "How are you?")

    def test_plain_question_is_sent_without_prompt_wrapper(self) -> None:
        self.assertEqual(build_answer_prompt("How are you?"), "How are you?")

    def test_explicit_chat_context_is_labeled(self) -> None:
        self.assertEqual(
            build_answer_prompt("What did we discuss?", "Max: deployment"),
            "Контекст чата:\nMax: deployment\n\nВопрос:\nWhat did we discuss?",
        )

    def test_command_argument(self) -> None:
        self.assertEqual(command_argument("/roast_now @max"), "@max")
        self.assertEqual(command_argument("/roast_now"), "")

    def test_format_roast_target(self) -> None:
        self.assertEqual(format_roast_target("@max"), "@max")
        self.assertEqual(format_roast_target("maxim_user"), "@maxim_user")
        self.assertEqual(format_roast_target("Max Fullname"), "Max Fullname")


class AnswerPipelineAsyncTests(unittest.IsolatedAsyncioTestCase):
    params = GenerationParams(0.7, 0.9, None, None, None, None, None, None, 1800)

    async def test_plain_answer_needs_one_call_without_api_formatting(self) -> None:
        llm = FakeLlm("Direct answer.")
        answer = await generate_clean_answer(
            llm,
            "question",
            system_prompt="answer system",
            model=ANSWER_MODEL,
            params=self.params,
        )
        self.assertEqual(answer, "Direct answer.")
        self.assertEqual(len(llm.calls), 1)
        self.assertEqual(llm.calls[0][1]["system_prompt"], "answer system")
        self.assertNotIn("response_format", llm.calls[0][1])
        self.assertNotIn("require_supported_parameters", llm.calls[0][1])
        self.assertEqual(llm.calls[0][1]["model"], ANSWER_MODEL)
        self.assertEqual(llm.calls[0][1]["params"].top_p, 0.9)
        self.assertIsNone(llm.calls[0][1]["params"].top_k)
        self.assertIsNone(llm.calls[0][1]["params"].repetition_penalty)
        self.assertIsNone(llm.calls[0][1]["params"].min_p)
        self.assertIsNone(llm.calls[0][1]["params"].top_a)
        self.assertEqual(llm.calls[0][1]["params"].max_tokens, 1800)

    async def test_roleplay_answer_is_rejected(self) -> None:
        llm = FakeLlm("Khan: Final answer.")
        with self.assertRaises(AnswerExtractionError):
            await generate_clean_answer(
                llm,
                "question",
                system_prompt="answer system",
                model=ANSWER_MODEL,
                params=self.params,
            )
        self.assertEqual(len(llm.calls), 1)


if __name__ == "__main__":
    unittest.main()
