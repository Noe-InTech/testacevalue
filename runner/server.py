"""Petit serveur EU pour lancer compare_tennis_aces_vs_fanduel.py en live."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "runner" / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
RESULT_JSON = DATA_DIR / "latest_aces.json"
STATUS_JSON = DATA_DIR / "run_status.json"
LOCK = threading.Lock()
RUNNING = False


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_status(status: str, message: str, *, match_filter: str = "") -> None:
    payload = {
        "status": status,
        "message": message,
        "match_filter": match_filter,
        "updated_at": utc_now(),
    }
    if status == "success" and RESULT_JSON.is_file():
        data = json.loads(RESULT_JSON.read_text(encoding="utf-8"))
        payload["generated_at"] = data.get("generated_at", "")
        payload["comparable_count"] = data.get("comparable_count", 0)
        payload["fr_higher_count"] = data.get("fr_higher_count", 0)
    STATUS_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def run_compare(match_filter: str) -> None:
    global RUNNING
    try:
        write_status("running", "Comparaison live en cours...", match_filter=match_filter)
        cmd = [sys.executable, str(ROOT / "compare_tennis_aces_vs_fanduel.py"), "-o", str(RESULT_JSON.with_suffix(".csv"))]
        if match_filter:
            cmd.extend(["--match", match_filter])
        proc = subprocess.run(
            cmd,
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=180,
            check=False,
        )
        if proc.returncode != 0:
            detail = (proc.stderr or proc.stdout or "Erreur inconnue.")[-2000:]
            write_status("error", f"Echec live compare.\n{detail}", match_filter=match_filter)
            return
        write_status("success", "Comparaison live terminee.", match_filter=match_filter)
    except subprocess.TimeoutExpired:
        write_status(
            "error",
            "Comparaison live interrompue apres 3 minutes (timeout).",
            match_filter=match_filter,
        )
    except Exception as exc:
        write_status("error", f"Exception runner: {exc}", match_filter=match_filter)
    finally:
        with LOCK:
            RUNNING = False


def read_json(path: Path, fallback: dict[str, Any]) -> dict[str, Any]:
    if not path.is_file():
        return fallback
    return json.loads(path.read_text(encoding="utf-8"))


class Handler(BaseHTTPRequestHandler):
    server_version = "AcesRunner/1.0"

    def _json_response(self, code: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _authorized(self) -> bool:
        secret = os.environ.get("RUNNER_SECRET", "").strip()
        if not secret:
            return False
        header = self.headers.get("X-Runner-Secret", "").strip()
        return header == secret

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path != "/api/results":
            self._json_response(404, {"error": "Not found"})
            return
        payload = read_json(
            RESULT_JSON,
            {
                "source": "tennis_aces_comparable",
                "generated_at": "",
                "comparable_count": 0,
                "fr_higher_count": 0,
                "comparables": [],
                "fr_higher_comparables": [],
            },
        )
        status = read_json(
            STATUS_JSON,
            {"status": "idle", "message": "Aucune comparaison lancee.", "updated_at": ""},
        )
        self._json_response(200, {"payload": payload, "status": status, "fetched_at": utc_now()})

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if path != "/api/trigger":
            self._json_response(404, {"error": "Not found"})
            return
        if not self._authorized():
            self._json_response(401, {"error": "Secret incorrect."})
            return

        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length) if length else b"{}"
        try:
            body = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            self._json_response(400, {"error": "JSON invalide."})
            return

        match_filter = str(body.get("match", "")).strip()
        global RUNNING
        with LOCK:
            if RUNNING:
                self._json_response(409, {"error": "Une comparaison est deja en cours."})
                return
            RUNNING = True

        thread = threading.Thread(target=run_compare, args=(match_filter,), daemon=True)
        thread.start()
        self._json_response(200, {"ok": True, "mode": "live", "started_at": utc_now()})

    def log_message(self, format: str, *args: Any) -> None:
        return


def main() -> None:
    host = os.environ.get("RUNNER_HOST", "0.0.0.0")
    port = int(os.environ.get("RUNNER_PORT", "8787"))
    if not os.environ.get("RUNNER_SECRET", "").strip():
        raise SystemExit("RUNNER_SECRET manquant.")
    if not (ROOT / "compare_tennis_aces_vs_fanduel.py").is_file():
        raise SystemExit(f"Repo introuvable: {ROOT}")
    write_status("idle", "Runner pret.")
    server = ThreadingHTTPServer((host, port), Handler)
    print(f"Aces runner live sur http://{host}:{port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
