from __future__ import annotations

import unittest

from bot.horoscope import split_horoscope_by_participant


class HoroscopeSplitTests(unittest.TestCase):
    def test_splits_one_llm_response_into_participant_messages(self) -> None:
        text = (
            "<b>SVOй персональный гороскоп</b>\n\n"
            "🔮 @morchao: сегодня день странных решений.\n\n"
            "- @spitllYY: звезды советуют не спорить с будильником."
        )

        messages = split_horoscope_by_participant(text, ["@morchao", "@spitllYY"])

        self.assertEqual(len(messages), 2)
        self.assertIn("@morchao", messages[0])
        self.assertNotIn("@spitllYY", messages[0])
        self.assertIn("@spitllYY", messages[1])
        self.assertTrue(messages[0].startswith("<b>SVOй персональный гороскоп</b>"))

    def test_keeps_full_text_when_participants_cannot_be_detected(self) -> None:
        text = "Общий гороскоп без явных тегов."

        self.assertEqual(split_horoscope_by_participant(text, ["@a", "@b"]), [text])


if __name__ == "__main__":
    unittest.main()
