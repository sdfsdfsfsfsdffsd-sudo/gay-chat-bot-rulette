from __future__ import annotations

import unittest
from types import SimpleNamespace

from bot.userbot import _resolve_target_dialog


class FakeClient:
    def __init__(self, dialogs) -> None:
        self.dialogs = dialogs

    async def get_input_entity(self, target):
        raise ValueError(f"No cached entity for {target}")

    async def iter_dialogs(self):
        for dialog in self.dialogs:
            yield dialog


class UserbotTests(unittest.IsolatedAsyncioTestCase):
    async def test_target_chat_is_resolved_from_user_dialogs_without_entity_cache(self) -> None:
        expected = object()
        client = FakeClient([
            SimpleNamespace(id=-100111, input_entity=object()),
            SimpleNamespace(id=-100222, input_entity=expected),
        ])

        target = await _resolve_target_dialog(client, -100222)

        self.assertIs(target, expected)

    async def test_target_chat_requires_user_account_membership(self) -> None:
        client = FakeClient([])

        with self.assertRaisesRegex(ValueError, "Add that account to the destination chat"):
            await _resolve_target_dialog(client, -100222)


if __name__ == "__main__":
    unittest.main()
