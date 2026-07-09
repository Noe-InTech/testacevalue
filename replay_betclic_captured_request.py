"""Template de replay pour une vraie requête Betclic capturée au navigateur.

Mode d'emploi:
1. Ouvrir DevTools Network sur une page match Betclic.
2. Cliquer l'onglet `Points & Service`.
3. Copier la requête exacte.
4. Remplir `REQUEST_URL`, `REQUEST_HEADERS`, `REQUEST_BODY_TEXT`.
5. Lancer ce script pour vérifier la réponse hors navigateur.
"""

from __future__ import annotations

import base64
import json
from pathlib import Path

import requests

REQUEST_URL = ""
REQUEST_HEADERS: dict[str, str] = {
    # Exemples typiques:
    # "content-type": "application/grpc-web-text",
    # "x-grpc-web": "1",
    # "x-user-agent": "grpc-web-javascript/0.1",
    # "authorization": "Bearer ...",
    # "origin": "https://www.betclic.fr",
    # "referer": "https://www.betclic.fr/tennis-stennis/...",
}
REQUEST_BODY_TEXT = ""

OUTPUT_DIR = Path(__file__).parent / "output"


def decode_grpc_web_text(payload: bytes) -> bytes:
    text = payload.decode("ascii", errors="ignore")
    text = "".join(text.split())
    return base64.b64decode(text) if text else b""


def parse_grpc_web_frames(payload: bytes) -> list[dict[str, str | int]]:
    frames: list[dict[str, str | int]] = []
    index = 0
    while index + 5 <= len(payload):
        frame_type = payload[index]
        frame_len = int.from_bytes(payload[index + 1 : index + 5], "big")
        start = index + 5
        end = start + frame_len
        if end > len(payload):
            break
        frame_body = payload[start:end]
        frames.append(
            {
                "frame_type": frame_type,
                "frame_len": frame_len,
                "preview_utf8": frame_body[:300].decode("utf-8", errors="replace"),
                "preview_hex": frame_body[:120].hex(),
            }
        )
        index = end
    return frames


def main() -> int:
    if not REQUEST_URL or not REQUEST_HEADERS or not REQUEST_BODY_TEXT:
        raise SystemExit("Remplis REQUEST_URL, REQUEST_HEADERS et REQUEST_BODY_TEXT avant execution.")

    response = requests.post(
        REQUEST_URL,
        data=REQUEST_BODY_TEXT.encode("ascii"),
        headers=REQUEST_HEADERS,
        timeout=30,
    )
    print("status", response.status_code)
    print("content-type", response.headers.get("content-type"))
    print("grpc-status", response.headers.get("grpc-status"))

    raw_payload = response.content
    if "grpc-web-text" in (response.headers.get("content-type") or ""):
        raw_payload = decode_grpc_web_text(raw_payload)

    frames = parse_grpc_web_frames(raw_payload)
    result = {
        "url": REQUEST_URL,
        "status_code": response.status_code,
        "response_headers": dict(response.headers),
        "frames": frames,
    }
    OUTPUT_DIR.mkdir(exist_ok=True)
    out_path = OUTPUT_DIR / "betclic_captured_request_replay.json"
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print("frames", len(frames))
    print("output", out_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
