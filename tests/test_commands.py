from __future__ import annotations

import unittest
from types import SimpleNamespace

from aiogram.types import BotCommandScopeChat, BotCommandScopeChatMember, BotCommandScopeDefault

from bot.commands import available_commands, can_use_command, commands_text, register_bot_commands


class FakeBot:
    def __init__(self) -> None:
        self.calls: list[tuple[list, object]] = []

    async def set_my_commands(self, commands, *, scope) -> None:
        self.calls.append((commands, scope))


class CommandRegistryTests(unittest.TestCase):
    def test_public_and_admin_command_lists_are_separate(self) -> None:
        public_names = {command.name for command in available_commands(False)}
        admin_names = {command.name for command in available_commands(True)}

        self.assertEqual(public_names, {"start", "commands", "bully", "word_stats_now", "alabuga"})
        self.assertIn("admin", admin_names)
        self.assertIn("conspiracy_now", admin_names)
        self.assertIn("forward_config", admin_names)
        self.assertIn("bully_text", admin_names)
        self.assertIn("bully_target", admin_names)
        self.assertNotIn("admin", public_names)
        self.assertNotIn("alabuga_random", public_names)

    def test_aliases_follow_primary_command_role(self) -> None:
        self.assertTrue(can_use_command("alabuga", False))
        self.assertTrue(can_use_command("alabuga_random", False))
        self.assertFalse(can_use_command("runtime_config", False))

    def test_commands_text_only_shows_commands_for_role(self) -> None:
        public_text = commands_text(False)
        admin_text = commands_text(True)

        self.assertIn("/alabuga - Случайный пост Алабуга Политех", public_text)
        self.assertIn("/bully - Забуллить жертву", public_text)
        self.assertNotIn("/admin", public_text)
        self.assertIn("/admin", admin_text)
        self.assertIn("<b>Для администраторов</b>", admin_text)


class CommandRegistrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_registers_default_and_per_admin_scopes(self) -> None:
        bot = FakeBot()
        settings = SimpleNamespace(admin_user_ids={10, 20}, bot_chat_id=-100123)

        await register_bot_commands(bot, settings)

        self.assertEqual(len(bot.calls), 5)
        self.assertIsInstance(bot.calls[0][1], BotCommandScopeDefault)
        self.assertEqual(len(bot.calls[0][0]), 5)
        self.assertEqual(sum(isinstance(scope, BotCommandScopeChat) for _, scope in bot.calls), 2)
        self.assertEqual(sum(isinstance(scope, BotCommandScopeChatMember) for _, scope in bot.calls), 2)

    async def test_empty_admin_list_exposes_full_menu_to_match_authorization(self) -> None:
        bot = FakeBot()
        settings = SimpleNamespace(admin_user_ids=set(), bot_chat_id=None)

        await register_bot_commands(bot, settings)

        self.assertEqual(len(bot.calls), 1)
        self.assertIsInstance(bot.calls[0][1], BotCommandScopeDefault)
        self.assertGreater(len(bot.calls[0][0]), 5)


if __name__ == "__main__":
    unittest.main()
