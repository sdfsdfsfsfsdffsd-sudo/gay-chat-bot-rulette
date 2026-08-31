from __future__ import annotations

import unittest
from types import SimpleNamespace

from bot.answer_pipeline import (
    AnswerExtractionError,
    extract_valid_final_answer,
    generate_clean_answer,
)
from bot.config import GenerationParams
from bot.handlers import (
    build_answer_prompt,
    build_short_reply_answer_prompt,
    build_runtime_config_text,
    clean_question_text,
    command_argument,
    format_bully_target,
)


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
        self.assertEqual(command_argument("/bully @max"), "@max")
        self.assertEqual(command_argument("/bully"), "")

    def test_format_bully_target(self) -> None:
        self.assertEqual(format_bully_target("@max"), "@max")
        self.assertEqual(format_bully_target("maxim_user"), "@maxim_user")
        self.assertEqual(format_bully_target("Max Fullname"), "Max Fullname")

    def test_runtime_config_text_shows_effective_model_and_prompt_hash(self) -> None:
        settings = SimpleNamespace(
            answer_model="answer/model",
            summary_model="summary/model",
            conspiracy_model="new/conspiracy-model",
            horoscope_model="horoscope/model",
            answer_web_search_enabled=True,
            summary_enabled=True,
            horoscope_enabled=False,
            joke_a_enabled=True,
            joke_b_enabled=True,
            conspiracy_enabled=True,
            word_stats_enabled=True,
            auto_bully_enabled=False,
            alabuga_enabled=True,
            **{
                f"{service}_params": SimpleNamespace(
                    temperature=0.85,
                    top_p=0.95,
                    top_k=None,
                    presence_penalty=0.0,
                    frequency_penalty=0.05,
                    repetition_penalty=None,
                    max_tokens=900,
                )
                for service in ("answer", "summary", "conspiracy", "horoscope")
            },
        )
        prompts = SimpleNamespace(
            answer_system="",
            summary_system="",
            conspiracy_system="new conspiracy system prompt",
            horoscope_system="",
        )

        text = build_runtime_config_text(settings, prompts)

        self.assertIn("conspiracy: model=new/conspiracy-model", text)
        self.assertIn("system_sha256=4e9f857599c9", text)
        self.assertIn("system_chars=28", text)
        self.assertIn("temperature=0.85", text)
        self.assertIn("answer_web_search_enabled=True", text)
        self.assertIn("automations: summary=True | horoscope=False", text)

    def test_short_reply_prompt_is_short_answer_instruction(self) -> None:
        text = build_short_reply_answer_prompt("Ну и?", "Max: Уже готово\nБот: Проверь результат")

        self.assertIn("одним коротким предложением", text)
        self.assertIn("Контекст чата:\nMax: Уже готово\nБот: Проверь результат", text)
        self.assertIn("Вопрос:\nНу и?", text)
        self.assertIn("Ну и?", text)


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
            web_search=True,
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
        self.assertTrue(llm.calls[0][1]["web_search"])

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
