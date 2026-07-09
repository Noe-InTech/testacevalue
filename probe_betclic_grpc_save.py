"""Save decoded Betclic gRPC payload for inspection."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from betclic_client import BetclicClient
from betclic_grpc import extract_payload_from_frames, fetch_match_grpc_frames

MATCH_URL = (
    "https://www.betclic.fr/tennis-stennis/wimbledon-h-c24/"
    "jannik-sinner-novak-djokovic-m1163187647176704"
)
OUT = Path(__file__).parent / "output" / "betclic_grpc_payload.json"


def json_safe(value: Any) -> Any:
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [json_safe(item) for item in value]
    return value


def main() -> None:
    client = BetclicClient()
    response = client.session.get(MATCH_URL, timeout=30)
    ng_state = client.extract_ng_state(response.text)
    config = ng_state["app-context"]["appSettings"]
    match_id = str(client.find_match_grpc_payload(ng_state)["match"]["matchId"])
    token = client.session.cookies.get("BC-TOKEN", "")
    frames = fetch_match_grpc_frames(
        client.session,
        grpc_offering_url=str(config["grpcOfferingUrl"]),
        match_id=match_id,
        referer=MATCH_URL,
        token=token,
        category_id=None,
    )
    payload = extract_payload_from_frames(frames)
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(json_safe(payload), ensure_ascii=False, indent=2), encoding="utf-8")
    print("saved", OUT, "size", OUT.stat().st_size)


if __name__ == "__main__":
    main()
