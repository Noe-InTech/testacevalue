"""Inspect decoded Betclic protobuf structure."""

from __future__ import annotations

import json
from typing import Any

from betclic_client import BetclicClient
from betclic_grpc import extract_payload_from_frames, fetch_match_grpc_frames

MATCH_URL = (
    "https://www.betclic.fr/tennis-stennis/wimbledon-h-c24/"
    "jannik-sinner-novak-djokovic-m1163187647176704"
)


def summarize(node: Any, depth: int = 0, max_depth: int = 4) -> Any:
    if depth >= max_depth:
        return "..."
    if isinstance(node, dict):
        return {str(key): summarize(value, depth + 1, max_depth) for key, value in list(node.items())[:12]}
    if isinstance(node, list):
        return [summarize(item, depth + 1, max_depth) for item in node[:3]]
    if isinstance(node, bytes):
        return f"bytes:{len(node)}"
    return node


def main() -> None:
    client = BetclicClient()
    response = client.session.get(MATCH_URL, timeout=30)
    ng_state = client.extract_ng_state(response.text)
    config = ng_state["app-context"]["appSettings"]
    match_id = str(client.find_match_grpc_payload(ng_state)["match"]["matchId"])
    token = client.session.cookies.get("BC-TOKEN", "")

    for category_id in ("ca_ten_ptss",):
        frames = fetch_match_grpc_frames(
            client.session,
            grpc_offering_url=str(config["grpcOfferingUrl"]),
            match_id=match_id,
            referer=MATCH_URL,
            token=token,
            category_id=category_id,
        )
        payload = extract_payload_from_frames(frames)
        if not payload:
            print("no payload", category_id)
            continue
        print(json.dumps(summarize(payload), ensure_ascii=False, indent=2)[:12000])


if __name__ == "__main__":
    main()
