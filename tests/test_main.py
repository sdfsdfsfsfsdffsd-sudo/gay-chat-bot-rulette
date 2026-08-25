from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from bot.main import SETTINGS_SCHEMA_VERSION_KEY, migrate_runtime_settings
from bot.prompts import ANSWER_SYSTEM_PROMPT
from bot.storage import Storage


class RuntimeSettingsMigrationTests(unittest.IsolatedAsyncioTestCase):
    async def make_storage(self, temp_dir: str) -> Storage:
        storage = Storage(Path(temp_dir) / "bot.sqlite3")
        await storage.init()
        return storage

    async def test_roast_settings_are_migrated_to_bully_names(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = await self.make_storage(temp_dir)
            await storage.set_setting_override("TARGET_USERNAME", "max")
            await storage.set_setting_override("ROAST_EVERY_MINUTES", "90")
            await storage.set_setting_override("ROAST_PROBABILITY", "0.4")
            await migrate_runtime_settings(storage, object(), await storage.settings_overrides())
            migrated = await storage.settings_overrides()

        self.assertEqual(migrated["BULLY_TARGET_USERNAME"], "max")
        self.assertEqual(migrated["BULLY_EVERY_MINUTES"], "90")
        self.assertEqual(migrated["BULLY_PROBABILITY"], "0.4")
        self.assertNotIn("TARGET_USERNAME", migrated)
        self.assertNotIn("ROAST_PROBABILITY", migrated)
        self.assertEqual(migrated[SETTINGS_SCHEMA_VERSION_KEY], "3")

    async def test_existing_bully_setting_is_not_overwritten(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = await self.make_storage(temp_dir)
            await storage.set_setting_override("TARGET_USERNAME", "legacy")
            await storage.set_setting_override("BULLY_TARGET_USERNAME", "current")
            await migrate_runtime_settings(storage, object(), await storage.settings_overrides())
            migrated = await storage.settings_overrides()

        self.assertEqual(migrated["BULLY_TARGET_USERNAME"], "current")

    async def test_obsolete_image_and_joke_settings_are_removed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = await self.make_storage(temp_dir)
            await storage.set_setting_override("RANDOM_IMAGE_ENABLED", "true")
            await storage.set_setting_override("JOKE_MODEL", "old/model")
            await storage.set_prompt_override("JOKE_A_PROMPT_TEXT", "old prompt")
            await migrate_runtime_settings(storage, object(), await storage.settings_overrides())
            settings = await storage.settings_overrides()
            prompts = await storage.prompt_overrides()

        self.assertNotIn("RANDOM_IMAGE_ENABLED", settings)
        self.assertNotIn("JOKE_MODEL", settings)
        self.assertNotIn("JOKE_A_PROMPT_TEXT", prompts)

    async def test_legacy_venice_conspiracy_system_prompt_is_removed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = await self.make_storage(temp_dir)
            await storage.set_prompt_override("CONSPIRACY_SYSTEM_PROMPT_TEXT", ANSWER_SYSTEM_PROMPT)
            await migrate_runtime_settings(storage, object(), await storage.settings_overrides())
            prompts = await storage.prompt_overrides()

        self.assertNotIn("CONSPIRACY_SYSTEM_PROMPT_TEXT", prompts)

    async def test_custom_conspiracy_system_prompt_is_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = await self.make_storage(temp_dir)
            await storage.set_prompt_override("CONSPIRACY_SYSTEM_PROMPT_TEXT", "custom conspiracy system")
            await migrate_runtime_settings(storage, object(), await storage.settings_overrides())
            prompts = await storage.prompt_overrides()

        self.assertEqual(prompts["CONSPIRACY_SYSTEM_PROMPT_TEXT"], "custom conspiracy system")


if __name__ == "__main__":
    unittest.main()
