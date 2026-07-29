import tempfile
import unittest
from pathlib import Path
from unittest import mock

import runner.server as runner_server


class SelfUpdateTests(unittest.TestCase):
    def test_schedule_self_update_missing_script(self) -> None:
        missing = Path("/tmp/does-not-exist-self-update.sh")
        with mock.patch.object(runner_server, "SELF_UPDATE_SCRIPT", missing):
            with mock.patch.object(runner_server, "UPDATE_SCHEDULED", False):
                ok, message, payload = runner_server.schedule_self_update()
        self.assertFalse(ok)
        self.assertIn("introuvable", message)
        self.assertEqual(payload, {})

    def test_schedule_self_update_launches_detached(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            script = root / "self_update.sh"
            script.write_text("#!/bin/bash\necho ok\n", encoding="utf-8")
            status = root / "last_update.json"
            with mock.patch.object(runner_server, "SELF_UPDATE_SCRIPT", script), mock.patch.object(
                runner_server, "ROOT", root
            ), mock.patch.object(runner_server, "LAST_UPDATE_FILE", status), mock.patch.object(
                runner_server, "UPDATE_SCHEDULED", False
            ), mock.patch("runner.server.subprocess.Popen") as popen, mock.patch(
                "runner.server.subprocess.check_output", return_value="abc1234\n"
            ):
                ok, message, payload = runner_server.schedule_self_update()
            self.assertTrue(ok)
            self.assertTrue(payload.get("scheduled"))
            self.assertEqual(payload.get("before"), "abc1234")
            self.assertIn("redemarrer", message)
            popen.assert_called_once()
            self.assertTrue(status.is_file())


if __name__ == "__main__":
    unittest.main()
