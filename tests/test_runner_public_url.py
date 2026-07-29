import tempfile
import unittest
from pathlib import Path
from unittest import mock

import runner.server as runner_server


class ResolvePublicUrlTests(unittest.TestCase):
    def test_reads_latest_url_from_log(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            log = root / "cloudflared.log"
            url_file = root / "public_url.txt"
            log.write_text(
                "old https://old-name.trycloudflare.com\n"
                "new https://fresh-tunnel.trycloudflare.com\n",
                encoding="utf-8",
            )
            with mock.patch.object(runner_server, "CLOUDFLARED_LOG", log), mock.patch.object(
                runner_server, "PUBLIC_URL_FILE", url_file
            ):
                url = runner_server.resolve_public_url()
            self.assertEqual(url, "https://fresh-tunnel.trycloudflare.com")
            self.assertEqual(url_file.read_text(encoding="utf-8").strip(), url)

    def test_falls_back_to_public_url_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            log = root / "missing.log"
            url_file = root / "public_url.txt"
            url_file.write_text("https://from-file.trycloudflare.com\n", encoding="utf-8")
            with mock.patch.object(runner_server, "CLOUDFLARED_LOG", log), mock.patch.object(
                runner_server, "PUBLIC_URL_FILE", url_file
            ):
                url = runner_server.resolve_public_url()
            self.assertEqual(url, "https://from-file.trycloudflare.com")


if __name__ == "__main__":
    unittest.main()
