"""Decode Betclic gRPC category responses."""

from __future__ import annotations

import json

from betclic_client import BetclicClient
from betclic_grpc import dump_frame_strings, extract_payload_from_frames, fetch_match_grpc_frames

MATCH_URL = (
    "https://www.betclic.fr/tennis-stennis/wimbledon-h-c24/"
    "jannik-sinner-novak-djokovic-m1163187647176704"
)


def main() -> None:
    client = BetclicClient()
    response = client.session.get(MATCH_URL, timeout=30)
    response.raise_for_status()
    ng_state = client.extract_ng_state(response.text)
    app_context = ng_state.get("app-context") or {}
    config = app_context.get("appSettings") or {}
    match_id = str(client.find_match_grpc_payload(ng_state).get("match", {}).get("matchId", ""))
    token = client.session.cookies.get("BC-TOKEN", "")

    for category_id in (None, "ca_ten_ptss"):
        frames = fetch_match_grpc_frames(
            client.session,
            grpc_offering_url=str(config["grpcOfferingUrl"]),
            match_id=match_id,
            referer=MATCH_URL,
            token=token,
            category_id=category_id,
        )
        payload = extract_payload_from_frames(frames)
        strings = []
        for frame_type, frame_body in frames:
            if frame_type == 0:
                strings.extend(dump_frame_strings(frame_body))
        marketish = sorted(
            {
                item
                for item in strings
                if any(token in item.lower() for token in ("ace", "break", "service", "jeux", "vainqueur"))
            }
        )
        print("=" * 80)
        print("category", category_id, "frames", len(frames), "payload", bool(payload))
        if payload and payload.get("match"):
            match = payload["match"]
            subs = match.get("subCategories") or match.get("11") or []
            print("subCategories type", type(subs), "count", len(subs) if isinstance(subs, list) else "n/a")
        print("marketish", marketish[:30])
        if payload:
            print(json.dumps(payload, ensure_ascii=False)[:4000])


if __name__ == "__main__":
    main()
