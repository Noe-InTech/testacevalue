"""Probe Winamax match-level markets via Socket.IO."""

from __future__ import annotations

import json
import uuid
from collections import Counter, defaultdict

import socketio

SOCKET_URL = "https://sports-eu-west-3.winamax.fr"
SOCKET_PATH = "/uof-sports-server/socket.io/"
MATCH_ID = "72318982"  # Sinner - Djokovic


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


def main() -> None:
    routes = [
        f"match:{MATCH_ID}",
        f"match/{MATCH_ID}",
        f"matches:{MATCH_ID}",
        f"sport:5/{MATCH_ID}",
    ]
    for route in routes:
        print(f"\n=== {route} ===")
        payload = fetch_route(route)
        if not payload:
            print("no payload")
            continue
        bets = payload.get("bets") or {}
        outcomes = payload.get("outcomes") or {}
        odds = payload.get("odds") or {}
        print(f"bets={len(bets)} outcomes={len(outcomes)} odds={len(odds)}")
        titles = Counter()
        for bet in bets.values():
            if str(bet.get("matchId")) != MATCH_ID:
                continue
            titles[bet.get("betTitle") or bet.get("betTypeName") or "?"] += 1
        print("bet titles for match:")
        for title, count in titles.most_common(40):
            print(f"  {count}x {title}")
        sample = [
            bet
            for bet in bets.values()
            if str(bet.get("matchId")) == MATCH_ID
        ][:3]
        print("sample bets:")
        print(json.dumps(sample, ensure_ascii=False, indent=2)[:2500])


if __name__ == "__main__":
    main()
