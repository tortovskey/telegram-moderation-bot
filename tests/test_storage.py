import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch


class StorageTests(unittest.TestCase):
    def test_restart_preserves_reputation_and_active_blocks(self):
        config = dict(BOT_TOKEN="test", CHANNEL_ID="test", ADMIN_SECRET_WORD="test",
                      ADMIN_ACCESS_CODE="test", MAIN_ADMIN_ID="1")
        with patch.dict(os.environ, config):
            from tg_bot import state
            from tg_bot.services import reputation, storage

        user_id = 5100000001
        until = time.time() + 3600
        with (
            tempfile.TemporaryDirectory() as tmp,
            patch.object(storage, "DATA_FILE", Path(tmp) / "data.json"),
            patch.object(storage, "BACKUP_FILE", Path(tmp) / "backup.json"),
            patch.object(state, "user_reputation", {user_id: 4}),
            patch.object(state, "user_blocks", {user_id: until}),
        ):
            self.assertTrue(storage.save_bot_data())
            state.user_reputation.clear()
            state.user_blocks.clear()
            self.assertTrue(storage.load_bot_data())
            self.assertEqual(reputation.get_user_reputation(user_id), 4)
            self.assertTrue(reputation.is_user_blocked(user_id))
            self.assertEqual(state.user_blocks, {user_id: until})
