from __future__ import annotations

import unittest

from bot.bully import render_bully_message


class BullyTemplateTests(unittest.TestCase):
    def test_render_bully_message_substitutes_target_and_username(self) -> None:
        text = render_bully_message("Hello {target}, short name {username}", "@max")

        self.assertEqual(text, "Hello @max, short name max")

    def test_invalid_template_falls_back_to_plain_suffix(self) -> None:
        text = render_bully_message("bad {missing}", "@max")

        self.assertEqual(text, "@max, bad {missing}")


if __name__ == "__main__":
    unittest.main()
