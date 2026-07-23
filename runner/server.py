"""Serveur EU pour lancer les comparaisons live (tennis + WNBA)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
DATA_DIR = ROOT / "runner" / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
LOCK = threading.Lock()
RUNNING = False
CURRENT_SPORT = ""
CURRENT_PROC: subprocess.Popen[str] | None = None
CANCEL_REQUESTED = False

from atomic_json import write_json_atomic  # noqa: E402


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
        timeout=2700,
    ),
    "wnba": SportConfig(
        key="wnba",
        script="compare_wnba_props_vs_fanduel.py",
        result_json=DATA_DIR / "latest_wnba.json",
        status_json=DATA_DIR / "run_status_wnba.json",
        combined=False,
        timeout=600,
    ),
    "nba": SportConfig(
        key="nba",
        script="compare_nba_props_vs_fanduel.py",
        result_json=DATA_DIR / "latest_nba.json",
        status_json=DATA_DIR / "run_status_nba.json",
        combined=False,
        timeout=600,
    ),
}


STUCK_RUN_SECONDS = 20 * 60


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_json(path: Path, fallback: dict[str, Any]) -> dict[str, Any]:
    if not path.is_file():
        return fallback
    try:
        raw = path.read_text(encoding="utf-8").strip()
        if not raw:
            return fallback
        data = json.loads(raw)
        return data if isinstance(data, dict) else fallback
    except (json.JSONDecodeError, OSError):
        return fallback


def parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def write_status(
    sport: SportConfig,
    status: str,
    message: str,
    *,
    match_filter: str = "",
    run_started_at: str | None = None,
    clear_run_started_at: bool = False,
) -> None:
    existing = read_json(sport.status_json, {})
    payload: dict[str, Any] = {
        "status": status,
        "message": message,
        "match_filter": match_filter or str(existing.get("match_filter", "")),
        "sport": sport.key,
        "updated_at": utc_now(),
    }
    started = run_started_at or (None if clear_run_started_at else existing.get("run_started_at"))
    if started:
        payload["run_started_at"] = started
    if status == "success" and sport.result_json.is_file():
        data = read_json(sport.result_json, {})
        payload["generated_at"] = data.get("generated_at", "")
        payload["comparable_count"] = data.get("comparable_count", 0)
        payload["fr_higher_count"] = data.get("fr_higher_count", 0)
        payload["matches_done"] = data.get("matches_done", 0)
        payload["anchors_total"] = data.get("anchors_total", 0)
        payload["fr_only_count"] = data.get("fr_only_count", 0)
    write_json_atomic(sport.status_json, payload)


def wipe_result_file(sport: SportConfig) -> None:
    write_json_atomic(sport.result_json, empty_payload(sport))


def clear_running_lock(*, reason: str = "") -> None:
    global RUNNING, CURRENT_SPORT, CURRENT_PROC, CANCEL_REQUESTED
    with LOCK:
        RUNNING = False
        CURRENT_SPORT = ""
        CURRENT_PROC = None
        CANCEL_REQUESTED = False
    if reason:
        print(f"Runner lock liberé: {reason}")


def recover_stuck_run() -> bool:
    """Libere un run bloque (process mort ou timeout) pour pouvoir relancer."""
    global RUNNING, CURRENT_SPORT, CURRENT_PROC, CANCEL_REQUESTED
    with LOCK:
        if not RUNNING:
            return False
        proc = CURRENT_PROC
        sport_key = CURRENT_SPORT
        if proc is not None and proc.poll() is None:
            sport = SPORTS.get(sport_key) if sport_key else None
            status = read_json(sport.status_json, {}) if sport else {}
            started = parse_iso(str(status.get("run_started_at") or status.get("updated_at") or ""))
            if started is not None:
                age = (datetime.now(timezone.utc) - started).total_seconds()
                if age < STUCK_RUN_SECONDS:
                    return False
            else:
                return False
        # process mort ou run trop vieux
        RUNNING = False
        CURRENT_SPORT = ""
        CURRENT_PROC = None
        CANCEL_REQUESTED = False

    sport = SPORTS.get(sport_key) if sport_key else None
    if sport is not None:
        write_status(
            sport,
            "error",
            "Comparaison precedente bloquee — lock libere automatiquement.",
            clear_run_started_at=True,
        )
    print(f"Stuck run recovered ({sport_key or 'unknown'})")
    return True


def ensure_status_files() -> None:
    """Au demarrage: JSON valides + aucun statut 'running' fantome."""
    for sport in SPORTS.values():
        status = read_json(sport.status_json, {})
        if status.get("status") == "running":
            write_status(
                sport,
                "idle",
                "Runner redemarre — run precedent ignore.",
                clear_run_started_at=True,
            )
        elif not sport.status_json.is_file() or sport.status_json.stat().st_size == 0:
            write_status(sport, "idle", "Runner pret.")
        if not sport.result_json.is_file() or sport.result_json.stat().st_size == 0:
            wipe_result_file(sport)


def empty_payload(sport: SportConfig) -> dict[str, Any]:
    if sport.key in {"wnba", "nba"}:
        return {
            "source": f"{sport.key}_player_props_comparable",
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
    global RUNNING, CURRENT_SPORT, CURRENT_PROC, CANCEL_REQUESTED
    proc: subprocess.Popen[str] | None = None
    try:
        CANCEL_REQUESTED = False
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
        proc = subprocess.Popen(
            cmd,
            cwd=str(ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        with LOCK:
            CURRENT_PROC = proc
        try:
            stdout, stderr = proc.communicate(timeout=sport.timeout)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.communicate()
            write_status(
                sport,
                "error",
                f"Comparaison live interrompue apres {sport.timeout // 60} minutes (timeout).",
                match_filter=match_filter,
            )
            return
        finally:
            with LOCK:
                if CURRENT_PROC is proc:
                    CURRENT_PROC = None

        if CANCEL_REQUESTED:
            write_status(
                sport,
                "cancelled",
                "Comparaison annulee par l'utilisateur.",
                match_filter=match_filter,
                clear_run_started_at=True,
            )
            return

        if proc.returncode != 0:
            detail = (stderr or stdout or "Erreur inconnue.")[-2000:]
            current = read_json(sport.status_json, {})
            if current.get("status") not in {"error", "cancelled"}:
                write_status(
                    sport,
                    "error",
                    f"Echec live compare.\n{detail}",
                    match_filter=match_filter,
                )
            return
        current = read_json(sport.status_json, {})
        if current.get("status") not in {"success", "cancelled"}:
            write_status(
                sport,
                "success",
                "Comparaison live terminee.",
                match_filter=match_filter,
                clear_run_started_at=True,
            )
    except Exception as exc:
        if not CANCEL_REQUESTED:
            write_status(sport, "error", f"Exception runner: {exc}", match_filter=match_filter)
    finally:
        with LOCK:
            RUNNING = False
            CURRENT_SPORT = ""
            if proc is not None and CURRENT_PROC is proc:
                CURRENT_PROC = None
            CANCEL_REQUESTED = False


def request_cancel(sport_key: str = "") -> tuple[bool, str]:
    """Demande l'arret du processus de comparaison en cours."""
    global CANCEL_REQUESTED
    with LOCK:
        if not RUNNING:
            return False, "Aucune comparaison active."
        if sport_key and CURRENT_SPORT and sport_key != CURRENT_SPORT:
            return False, f"Comparaison {CURRENT_SPORT} en cours (pas {sport_key})."
        CANCEL_REQUESTED = True
        proc = CURRENT_PROC
        active_sport = CURRENT_SPORT

    sport = SPORTS.get(active_sport) if active_sport else None
    if sport is not None:
        write_status(sport, "running", "Arret de la comparaison en cours...", match_filter="")

    if proc is not None and proc.poll() is None:
        proc.terminate()
        deadline = time.time() + 5
        while time.time() < deadline and proc.poll() is None:
            time.sleep(0.2)
        if proc.poll() is None:
            proc.kill()

    return True, "Arret demande."


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
        if path == "/api/health":
            recover_stuck_run()
            with LOCK:
                busy = RUNNING
                sport = CURRENT_SPORT
            self._json_response(
                200,
                {
                    "ok": True,
                    "running": busy,
                    "sport": sport or "",
                    "fetched_at": utc_now(),
                },
            )
            return
        if path != "/api/results":
            self._json_response(404, {"error": "Not found"})
            return
        sport = self._resolve_sport(self.path)
        if sport is None:
            self._json_response(400, {"error": "Sport inconnu (tennis, wnba ou nba)."})
            return
        recover_stuck_run()
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
        if path == "/api/cancel":
            self._handle_cancel()
            return
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
            self._json_response(400, {"error": "Sport inconnu (tennis, wnba ou nba)."})
            return

        match_filter = str(body.get("match", "")).strip()
        global RUNNING, CURRENT_SPORT
        recover_stuck_run()
        with LOCK:
            if RUNNING:
                running_sport = CURRENT_SPORT or sport.key
                running_cfg = SPORTS.get(running_sport) or sport
                status = read_json(running_cfg.status_json, {})
                self._json_response(
                    409,
                    {
                        "error": (
                            f"Une comparaison {running_sport} est deja active."
                        ),
                        "already_running": True,
                        "sport": running_sport,
                        "started_at": status.get("run_started_at") or status.get("updated_at") or "",
                        "matches_done": status.get("matches_done", 0),
                        "anchors_total": status.get("anchors_total", 0),
                        "message": status.get("message", ""),
                    },
                )
                return
            RUNNING = True
            CURRENT_SPORT = sport.key

        started_at = utc_now()
        wipe_result_file(sport)
        write_status(
            sport,
            "running",
            "Comparaison live en cours...",
            match_filter=match_filter,
            run_started_at=started_at,
        )

        thread = threading.Thread(target=run_compare, args=(sport, match_filter), daemon=True)
        thread.start()
        self._json_response(
            200,
            {"ok": True, "mode": "live", "sport": sport.key, "started_at": started_at},
        )

    def _handle_cancel(self) -> None:
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

        sport_key = str(body.get("sport", "")).strip().lower()
        ok, message = request_cancel(sport_key)
        if not ok and sport_key and "en cours" in message:
            self._json_response(409, {"error": message})
            return
        self._json_response(
            200,
            {
                "ok": True,
                "cancelled": ok,
                "message": message,
                "sport": sport_key or CURRENT_SPORT or "",
            },
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
    clear_running_lock(reason="startup")
    ensure_status_files()
    for sport in SPORTS.values():
        current = read_json(sport.status_json, {})
        if current.get("status") != "idle":
            write_status(sport, "idle", "Runner pret.")
    server = ThreadingHTTPServer((host, port), Handler)
    print(f"Props runner live sur http://{host}:{port} (tennis + wnba + nba)")
    server.serve_forever()


if __name__ == "__main__":
    main()
