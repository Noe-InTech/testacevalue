"""Probe Winamax Socket.IO tennis feed."""

from __future__ import annotations

import json
import uuid
from pprint import pprint

import socketio

SOCKET_URL = "https://sports-eu-west-3.winamax.fr"
SOCKET_PATH = "/uof-sports-server/socket.io/"


def fetch_route(route: str, timeout: float = 12.0) -> dict | None:
    request_id = str(uuid.uuid4())
    result: dict | None = None

    sio = socketio.Client(logger=False, engineio_logger=False)

    @sio.on("m")
    def on_message(data):
        nonlocal result
        if isinstance(data, dict) and data.get("requestId") == request_id:
            result = data

    sio.connect(
        SOCKET_URL,
        transports=["websocket"],
        socketio_path=SOCKET_PATH,
        headers={"Origin": "https://www.winamax.fr"},
    )
    sio.emit("m", {"route": route, "requestId": request_id})
    sio.sleep(timeout)
    sio.disconnect()
    return result


def summarize(payload: dict) -> None:
    matches = payload.get("matches") or {}
    bets = payload.get("bets") or {}
    outcomes = payload.get("outcomes") or {}
    odds = payload.get("odds") or {}
    tournaments = payload.get("tournaments") or {}
    print(
        f"matches={len(matches)} bets={len(bets)} outcomes={len(outcomes)} "
        f"odds={len(odds)} tournaments={len(tournaments)}"
    )
    for match_id, match in list(matches.items())[:5]:
        title = match.get("title") or match.get("name") or match_id
        sport_id = match.get("sportId")
        print(f"  match {match_id}: {title!r} sportId={sport_id}")
    if bets:
        sample_bet = next(iter(bets.values()))
        print("  sample bet keys:", list(sample_bet.keys()))
        print("  sample bet:", json.dumps(sample_bet, ensure_ascii=False)[:400])


def main() -> None:
    routes = [
        "sport:5",
        "sports",
        "live",
        "top",
        "calendar",
        "sport:1",
    ]
    for route in routes:
        print(f"\n=== route={route} ===")
        try:
            payload = fetch_route(route)
        except Exception as exc:
            print(f"ERROR: {exc}")
            continue
        if not payload:
            print("no payload")
            continue
        summarize(payload)


if __name__ == "__main__":
    main()
