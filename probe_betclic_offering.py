"""Probe Betclic offering gRPC-web match endpoint."""

from __future__ import annotations

import json
import base64
from typing import Any

import blackboxprotobuf
import requests

from betclic_client import BetclicClient

MATCH_URL = (
    "https://www.betclic.fr/tennis-stennis/wimbledon-h-c24/"
    "jannik-sinner-novak-djokovic-m1163187647176704"
)


def encode_varint(value: int) -> bytes:
    output = bytearray()
    while True:
        to_write = value & 0x7F
        value >>= 7
        if value:
            output.append(to_write | 0x80)
        else:
            output.append(to_write)
            return bytes(output)


def encode_field_varint(field_number: int, value: int) -> bytes:
    return encode_varint((field_number << 3) | 0) + encode_varint(value)


def encode_field_string(field_number: int, value: str) -> bytes:
    data = value.encode("utf-8")
    return encode_varint((field_number << 3) | 2) + encode_varint(len(data)) + data


def build_get_match_request(match_id: str, language: str = "fr", category_id: str | None = None) -> bytes:
    message = bytearray()
    message.extend(encode_field_varint(1, int(match_id)))
    message.extend(encode_field_string(2, language))
    if category_id:
        message.extend(encode_field_string(3, category_id))
    return bytes(message)


def grpc_web_frame(message: bytes) -> bytes:
    return b"\x00" + len(message).to_bytes(4, "big") + message


def parse_grpc_web_frames(payload: bytes) -> list[tuple[int, bytes]]:
    frames: list[tuple[int, bytes]] = []
    index = 0
    while index + 5 <= len(payload):
        frame_type = payload[index]
        frame_len = int.from_bytes(payload[index + 1 : index + 5], "big")
        start = index + 5
        end = start + frame_len
        if end > len(payload):
            break
        frames.append((frame_type, payload[start:end]))
        index = end
    return frames


def decode_grpc_web_text(payload: bytes) -> bytes:
    text = payload.decode("ascii", errors="ignore")
    text = "".join(text.split())
    if not text:
        return b""
    return base64.b64decode(text)


def call_match_endpoint(category_id: str | None = None, path_suffix: str = "/offering.access.api.MatchService/GetMatchWithNotification") -> dict[str, Any]:
    client = BetclicClient()
    response = client.session.get(MATCH_URL, timeout=30)
    response.raise_for_status()
    html = response.text
    ng_state = client.extract_ng_state(html)
    payload = client.find_match_grpc_payload(ng_state)
    match = payload.get("match") or {}
    app_context = ng_state.get("app-context") or {}
    config = app_context.get("appSettings") if isinstance(app_context, dict) else None
    if not config:
        raise RuntimeError("Configuration grpcOfferingUrl introuvable")

    grpc_url = str(config["grpcOfferingUrl"]).rstrip("/")
    token = client.session.cookies.get("BC-TOKEN")
    if not token:
        raise RuntimeError("Cookie BC-TOKEN introuvable")

    request_message = build_get_match_request(
        str(match.get("matchId", "")),
        language=str(app_context.get("language", "fr") or "fr"),
        category_id=category_id,
    )
    request_body = base64.b64encode(grpc_web_frame(request_message))
    grpc_response = client.session.post(
        f"{grpc_url}{path_suffix}",
        data=request_body,
        headers={
            "Content-Type": "application/grpc-web-text",
            "Accept": "application/grpc-web-text",
            "X-Grpc-Web": "1",
            "X-User-Agent": "grpc-web-javascript/0.1",
            "authorization": f"Bearer {token}",
            "Origin": "https://www.betclic.fr",
            "Referer": MATCH_URL,
        },
        timeout=30,
    )

    raw_payload = grpc_response.content
    if "grpc-web-text" in grpc_response.headers.get("content-type", ""):
        raw_payload = decode_grpc_web_text(raw_payload)
    frames = parse_grpc_web_frames(raw_payload)
    decoded_data = []
    for frame_type, frame_body in frames:
        if frame_type == 0:
            try:
                message, typedef = blackboxprotobuf.decode_message(frame_body)
                decoded_data.append({"message": message, "typedef": typedef})
            except Exception as exc:  # pragma: no cover - debugging fallback
                decoded_data.append({"decode_error": str(exc), "raw_len": len(frame_body)})
        else:
            decoded_data.append({"trailer_type": frame_type, "raw": frame_body.decode("utf-8", errors="replace")})

    return {
        "grpc_url": grpc_url,
        "path_suffix": path_suffix,
        "category_id": category_id,
        "status_code": grpc_response.status_code,
        "headers": dict(grpc_response.headers),
        "frames_count": len(frames),
        "decoded": decoded_data,
        "categories": match.get("categories") or [],
    }


def main() -> None:
    paths = (
        "/offering.access.api.MatchService/GetMatchWithNotification",
        "/MatchService/GetMatchWithNotification",
        "/GetMatchWithNotification",
    )
    for path_suffix in paths:
        for category_id in (None, "ca_ten_ptss"):
            result = call_match_endpoint(category_id, path_suffix)
            print("=" * 80)
            print("path", path_suffix)
            print("category_id", category_id)
            print("status", result["status_code"])
            print("content-type", result["headers"].get("content-type"))
            print("grpc-status", result["headers"].get("grpc-status"))
            print("frames", result["frames_count"])
            print(json.dumps(result["decoded"][:2], ensure_ascii=False, indent=2)[:6000])


if __name__ == "__main__":
    main()
