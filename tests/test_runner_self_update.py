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

    def test_run_compare_logs_to_file_not_pipe(self) -> None:
        import subprocess

        with tempfile.TemporaryDirectory() as tmp:
            data = Path(tmp)
            sport = runner_server.SPORTS["nba"]
            proc = mock.Mock()
            proc.wait.return_value = 0
            proc.returncode = 0
            with mock.patch.object(runner_server, "DATA_DIR", data), mock.patch.object(
                runner_server, "write_status"
            ), mock.patch.object(
                runner_server, "read_json", return_value={"status": "success"}
            ), mock.patch("runner.server.subprocess.Popen", return_value=proc) as popen:
                runner_server.run_compare(sport, "wizards")
            kwargs = popen.call_args.kwargs
            self.assertIsNot(kwargs["stdout"], subprocess.PIPE)
            self.assertEqual(kwargs["stderr"], subprocess.STDOUT)
            self.assertEqual(kwargs["env"]["PYTHONUNBUFFERED"], "1")
            log = data / "compare_nba.log"
            self.assertIn("compare nba", log.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
