from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from bot.main import LEGACY_JOKE_MODEL, SETTINGS_SCHEMA_VERSION_KEY, migrate_runtime_settings
from bot.storage import Storage


class RuntimeSettingsMigrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_legacy_seeded_joke_model_is_migrated_once(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = Storage(Path(temp_dir) / "bot.sqlite3")
            await storage.init()
            await storage.set_setting_override("JOKE_MODEL", LEGACY_JOKE_MODEL)
            overrides = await storage.settings_overrides()

            await migrate_runtime_settings(
                storage,
                SimpleNamespace(joke_model="cognitivecomputations/dolphin-mistral-24b-venice-edition"),
                overrides,
            )
            migrated = await storage.settings_overrides()

        self.assertEqual(
            migrated["JOKE_MODEL"],
            "cognitivecomputations/dolphin-mistral-24b-venice-edition",
        )
        self.assertEqual(migrated[SETTINGS_SCHEMA_VERSION_KEY], "1")

    async def test_explicit_legacy_model_is_preserved_when_bootstrap_matches(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            storage = Storage(Path(temp_dir) / "bot.sqlite3")
            await storage.init()
            await storage.set_setting_override("JOKE_MODEL", LEGACY_JOKE_MODEL)

            await migrate_runtime_settings(
                storage,
                SimpleNamespace(joke_model=LEGACY_JOKE_MODEL),
                await storage.settings_overrides(),
            )
            migrated = await storage.settings_overrides()

        self.assertEqual(migrated["JOKE_MODEL"], LEGACY_JOKE_MODEL)


if __name__ == "__main__":
    unittest.main()
