"""Serveur EU pour lancer les comparaisons live (tennis + WNBA)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "runner" / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
LOCK = threading.Lock()
RUNNING = False
CURRENT_SPORT = ""


@dataclass(frozen=True)
class SportConfig:
    key: str
    script: str
    result_json: Path
    status_json: Path
    combined: bool
    timeout: int


SPORTS: dict[str, SportConfig] = {
    "tennis": SportConfig(
        key="tennis",
        script="compare_tennis_aces_vs_fanduel.py",
        result_json=DATA_DIR / "latest_aces.json",
        status_json=DATA_DIR / "run_status.json",
        combined=True,
        timeout=480,
    ),
    "wnba": SportConfig(
        key="wnba",
        script="compare_wnba_props_vs_fanduel.py",
        result_json=DATA_DIR / "latest_wnba.json",
        status_json=DATA_DIR / "run_status_wnba.json",
        combined=False,
        timeout=600,
    ),
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_json(path: Path, fallback: dict[str, Any]) -> dict[str, Any]:
    if not path.is_file():
        return fallback
    return json.loads(path.read_text(encoding="utf-8"))


def write_status(
    sport: SportConfig,
    status: str,
    message: str,
    *,
    match_filter: str = "",
) -> None:
    payload: dict[str, Any] = {
        "status": status,
        "message": message,
        "match_filter": match_filter,
        "sport": sport.key,
        "updated_at": utc_now(),
    }
    if status == "success" and sport.result_json.is_file():
        data = json.loads(sport.result_json.read_text(encoding="utf-8"))
        payload["generated_at"] = data.get("generated_at", "")
        payload["comparable_count"] = data.get("comparable_count", 0)
        payload["fr_higher_count"] = data.get("fr_higher_count", 0)
        payload["matches_done"] = data.get("matches_done", 0)
        payload["anchors_total"] = data.get("anchors_total", 0)
        payload["fr_only_count"] = data.get("fr_only_count", 0)
    sport.status_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def empty_payload(sport: SportConfig) -> dict[str, Any]:
    if sport.key == "wnba":
        return {
            "source": "wnba_player_props_comparable",
            "generated_at": "",
            "partial": True,
            "anchors_total": 0,
            "matches_done": 0,
            "comparable_count": 0,
            "fr_higher_count": 0,
            "value_count": 0,
            "fr_only_count": 0,
            "fd_only_count": 0,
            "comparables": [],
            "fr_higher_comparables": [],
            "value_comparables": [],
            "fr_only_comparables": [],
            "fd_only_comparables": [],
            "match_progress": [],
        }
    return {
        "source": "tennis_props_comparable",
        "generated_at": "",
        "partial": True,
        "anchors_total": 0,
        "matches_done": 0,
        "aces": {
            "source": "tennis_aces_comparable",
            "generated_at": "",
            "comparable_count": 0,
            "fr_higher_count": 0,
            "comparables": [],
            "fr_higher_comparables": [],
        },
        "breaks": {
            "source": "tennis_breaks_comparable",
            "generated_at": "",
            "comparable_count": 0,
            "fr_higher_count": 0,
            "comparables": [],
            "fr_higher_comparables": [],
        },
    }


def run_compare(sport: SportConfig, match_filter: str) -> None:
    global RUNNING, CURRENT_SPORT
    try:
        write_status(sport, "running", "Comparaison live en cours...", match_filter=match_filter)
        cmd = [
            sys.executable,
            str(ROOT / sport.script),
            "-o",
            str(sport.result_json.with_suffix(".csv")),
            "--progress-json",
            str(sport.result_json),
            "--status-json",
            str(sport.status_json),
        ]
        if sport.combined:
            cmd.append("--combined")
        if match_filter:
            cmd.extend(["--match", match_filter])
        proc = subprocess.run(
            cmd,
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=sport.timeout,
            check=False,
        )
        if proc.returncode != 0:
            detail = (proc.stderr or proc.stdout or "Erreur inconnue.")[-2000:]
            current = read_json(sport.status_json, {})
            if current.get("status") != "error":
                write_status(
                    sport,
                    "error",
                    f"Echec live compare.\n{detail}",
                    match_filter=match_filter,
                )
            return
        current = read_json(sport.status_json, {})
        if current.get("status") != "success":
            write_status(sport, "success", "Comparaison live terminee.", match_filter=match_filter)
    except subprocess.TimeoutExpired:
        write_status(
            sport,
            "error",
            f"Comparaison live interrompue apres {sport.timeout // 60} minutes (timeout).",
            match_filter=match_filter,
        )
    except Exception as exc:
        write_status(sport, "error", f"Exception runner: {exc}", match_filter=match_filter)
    finally:
        with LOCK:
            RUNNING = False
            CURRENT_SPORT = ""


class Handler(BaseHTTPRequestHandler):
    server_version = "PropsRunner/2.0"

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

    def _resolve_sport(self, path: str) -> SportConfig | None:
        query = parse_qs(urlparse(self.path).query)
        sport_key = str(query.get("sport", ["tennis"])[0]).strip().lower()
        return SPORTS.get(sport_key)

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path != "/api/results":
            self._json_response(404, {"error": "Not found"})
            return
        sport = self._resolve_sport(self.path)
        if sport is None:
            self._json_response(400, {"error": "Sport inconnu (tennis ou wnba)."})
            return
        payload = read_json(sport.result_json, empty_payload(sport))
        status = read_json(
            sport.status_json,
            {
                "status": "idle",
                "message": "Aucune comparaison lancee.",
                "sport": sport.key,
                "updated_at": "",
            },
        )
        self._json_response(
            200,
            {
                "payload": payload,
                "status": status,
                "sport": sport.key,
                "fetched_at": utc_now(),
            },
        )

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

        sport_key = str(body.get("sport", "tennis")).strip().lower()
        sport = SPORTS.get(sport_key)
        if sport is None:
            self._json_response(400, {"error": "Sport inconnu (tennis ou wnba)."})
            return

        match_filter = str(body.get("match", "")).strip()
        global RUNNING, CURRENT_SPORT
        with LOCK:
            if RUNNING:
                self._json_response(
                    409,
                    {
                        "error": (
                            f"Une comparaison {CURRENT_SPORT or 'en cours'} est deja active."
                        ),
                    },
                )
                return
            RUNNING = True
            CURRENT_SPORT = sport.key

        thread = threading.Thread(target=run_compare, args=(sport, match_filter), daemon=True)
        thread.start()
        self._json_response(
            200,
            {"ok": True, "mode": "live", "sport": sport.key, "started_at": utc_now()},
        )

    def log_message(self, format: str, *args: Any) -> None:
        return


def main() -> None:
    host = os.environ.get("RUNNER_HOST", "0.0.0.0")
    port = int(os.environ.get("RUNNER_PORT", "8787"))
    if not os.environ.get("RUNNER_SECRET", "").strip():
        raise SystemExit("RUNNER_SECRET manquant.")
    for sport in SPORTS.values():
        if not (ROOT / sport.script).is_file():
            raise SystemExit(f"Script introuvable: {sport.script}")
        write_status(sport, "idle", "Runner pret.")
    server = ThreadingHTTPServer((host, port), Handler)
    print(f"Props runner live sur http://{host}:{port} (tennis + wnba)")
    server.serve_forever()


if __name__ == "__main__":
    main()
