"""Test Betclic gRPC URL variants and X-BG headers."""

from __future__ import annotations

import base64

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


def build_get_match_request(
    match_id: str,
    language: str = "fr",
    category_id: str | None = None,
    supported_features: tuple[int, ...] = (1, 2, 3, 4, 5),
) -> bytes:
    message = bytearray()
    message.extend(encode_field_varint(1, int(match_id)))
    message.extend(encode_field_string(2, language))
    if category_id:
        message.extend(encode_field_string(3, category_id))
    for feature in supported_features:
        message.extend(encode_field_varint(4, feature))
    return bytes(message)


def grpc_web_frame(message: bytes) -> bytes:
    return b"\x00" + len(message).to_bytes(4, "big") + message


def main() -> None:
    client = BetclicClient()
    response = client.session.get(MATCH_URL, timeout=30)
    response.raise_for_status()
    ng_state = client.extract_ng_state(response.text)
    app_context = ng_state.get("app-context") or {}
    config = app_context.get("appSettings") or {}
    payload = client.find_match_grpc_payload(ng_state)
    match = payload.get("match") or {}
    match_id = str(match.get("matchId", ""))
    token = client.session.cookies.get("BC-TOKEN", "")
    grpc_base = str(config.get("grpcOfferingUrl", "")).rstrip("/")

    urls = [
        f"{grpc_base}/offering.access.api.MatchService/GetMatchWithNotification",
        f"{grpc_base}.MatchService/GetMatchWithNotification",
        "https://offering.begmedia.com/web/offering.access.api.MatchService/GetMatchWithNotification",
        "https://offering.begmedia.com/offering.access.api.MatchService/GetMatchWithNotification",
    ]

    body = base64.b64encode(grpc_web_frame(build_get_match_request(match_id, category_id="ca_ten_ptss")))
    headers = {
        "Content-Type": "application/grpc-web-text",
        "Accept": "application/grpc-web-text",
        "X-Grpc-Web": "1",
        "X-User-Agent": "grpc-web-javascript/0.1",
        "authorization": f"Bearer {token}",
        "Origin": "https://www.betclic.fr",
        "Referer": MATCH_URL,
        "X-BG-REGULATION": "FR",
        "X-BG-Ref-Brand": "BETCLIC",
        "X-BG-Ref-Regulator-Zone": "FR",
        "X-BG-Ref-Platform": "DESKTOP",
    }

    for url in urls:
        resp = client.session.post(url, data=body, headers=headers, timeout=30)
        print(url)
        print(" ", resp.status_code, resp.headers.get("grpc-status"), len(resp.content))
        if resp.status_code == 200:
            print(" ", resp.content[:120])


if __name__ == "__main__":
    main()
