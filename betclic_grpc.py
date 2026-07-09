"""Betclic offering gRPC-web client helpers."""

from __future__ import annotations

import base64
import struct
from typing import Any, Iterable

import requests

GRPC_PATH = "/offering.access.api.MatchService/GetMatchWithNotification"
DEFAULT_SUPPORTED_FEATURES = tuple(range(1, 9))


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
    supported_features: Iterable[int] = DEFAULT_SUPPORTED_FEATURES,
) -> bytes:
    message = bytearray()
    message.extend(encode_field_varint(1, int(match_id)))
    message.extend(encode_field_string(2, language))
    if category_id:
        message.extend(encode_field_string(3, category_id))
    for feature in supported_features:
        message.extend(encode_field_varint(4, int(feature)))
    return bytes(message)


def grpc_web_frame(message: bytes) -> bytes:
    return b"\x00" + len(message).to_bytes(4, "big") + message


def decode_grpc_web_text(payload: bytes) -> bytes:
    text = payload.decode("ascii", errors="ignore")
    text = "".join(text.split())
    return base64.b64decode(text) if text else b""


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


def betclic_bg_headers(referer: str) -> dict[str, str]:
    return {
        "X-BG-REGULATION": "FR",
        "X-BG-Ref-Brand": "BETCLIC",
        "X-BG-Ref-Regulator-Zone": "FR",
        "X-BG-Ref-Platform": "DESKTOP",
        "Origin": "https://www.betclic.fr",
        "Referer": referer,
    }


def _has_complete_grpc_frame(payload: bytes) -> bool:
    if len(payload) < 5:
        return False
    frame_len = int.from_bytes(payload[1:5], "big")
    return len(payload) >= 5 + frame_len


def fetch_match_grpc_frames(
    session: requests.Session,
    *,
    grpc_offering_url: str,
    match_id: str,
    referer: str,
    token: str,
    category_id: str | None = None,
    language: str = "fr",
    max_bytes: int = 2_000_000,
) -> list[tuple[int, bytes]]:
    request_body = base64.b64encode(
        grpc_web_frame(build_get_match_request(match_id, language=language, category_id=category_id))
    )
    headers = {
        "Content-Type": "application/grpc-web-text",
        "Accept": "application/grpc-web-text",
        "X-Grpc-Web": "1",
        "X-User-Agent": "grpc-web-javascript/0.1",
        "authorization": f"Bearer {token}",
        "grpc-timeout": "4000m",
        **betclic_bg_headers(referer),
    }

    raw = b""
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            response = session.post(
                f"{grpc_offering_url.rstrip('/')}{GRPC_PATH}",
                data=request_body,
                headers=headers,
                timeout=12,
            )
            if response.status_code != 200:
                raise RuntimeError(
                    f"Betclic gRPC {response.status_code}: {response.text[:200]}"
                )
            raw = response.content
            if raw:
                break
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as exc:
            last_error = exc
            continue
    if not raw:
        if last_error:
            raise RuntimeError(f"Betclic gRPC timeout: {last_error}") from last_error
        raise RuntimeError("Betclic gRPC empty response")
    if "grpc-web-text" in (response.headers.get("content-type") or ""):
        raw = decode_grpc_web_text(raw)
    if max_bytes and len(raw) > max_bytes:
        raw = raw[:max_bytes]
    return parse_grpc_web_frames(raw)


def _walk_nodes(node: Any) -> Iterable[dict[str, Any]]:
    if isinstance(node, dict):
        if "betslipName" in node or "name" in node:
            yield node
        for value in node.values():
            yield from _walk_nodes(value)
    elif isinstance(node, list):
        for item in node:
            yield from _walk_nodes(item)


def decode_match_payload_message(frame_body: bytes) -> dict[str, Any] | None:
    try:
        import blackboxprotobuf
    except ImportError:
        return None
    try:
        message, _typedef = blackboxprotobuf.decode_message(frame_body)
    except Exception:
        return None
    if not isinstance(message, dict):
        return None
    payload = message.get("1")
    if isinstance(payload, dict):
        match = payload.get("1")
        if isinstance(match, dict):
            return {"match": _normalize_protobuf_match(match)}
    match = message.get("1")
    if isinstance(match, dict) and any(key in match for key in ("10", "11", "sub_categories")):
        return {"match": _normalize_protobuf_match(match)}
    return {"raw": message}


def _normalize_protobuf_match(match: dict[str, Any]) -> dict[str, Any]:
    """Best-effort normalization of decoded protobuf match to SSR-like dict."""
    normalized = dict(match)
    if "11" in match and "subCategories" not in match:
        normalized["subCategories"] = match.get("11")
    if "10" in match and "categories" not in match:
        normalized["categories"] = match.get("10")
    if "9" in match and "contestants" not in match:
        normalized["contestants"] = match.get("9")
    if "2" in match and "name" not in match:
        normalized["name"] = match.get("2")
    if "3" in match and "matchDateUtc" not in match:
        normalized["matchDateUtc"] = match.get("3")
    if "7" in match and "openMarketCount" not in match:
        normalized["openMarketCount"] = match.get("7")
    if "1" in match and "matchId" not in match:
        normalized["matchId"] = match.get("1")
    return normalized


def extract_payload_from_frames(frames: list[tuple[int, bytes]]) -> dict[str, Any] | None:
    for frame_type, frame_body in frames:
        if frame_type != 0:
            continue
        payload = decode_match_payload_message(frame_body)
        if payload:
            return payload
    return None


def protobuf_to_ssr_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Convert decoded protobuf payload into SSR-like structure for market extraction."""
    match = payload.get("match")
    if not isinstance(match, dict):
        return payload

    converted_match = _convert_protobuf_node(match)
    if not isinstance(converted_match, dict):
        return payload

    sub_categories = converted_match.get("subCategories") or []
    if isinstance(sub_categories, dict):
        sub_categories = list(sub_categories.values())
    normalized_subs = []
    for item in sub_categories:
        normalized = _normalize_grpc_subcategory(item)
        if normalized:
            normalized_subs.append(normalized)
    if normalized_subs:
        converted_match["subCategories"] = normalized_subs
    elif not isinstance(sub_categories, list):
        converted_match["subCategories"] = []

    categories = converted_match.get("categories") or []
    if isinstance(categories, dict):
        categories = list(categories.values())
    normalized_categories = []
    for item in categories:
        normalized = _normalize_grpc_category(item)
        if normalized:
            normalized_categories.append(normalized)
    if normalized_categories:
        converted_match["categories"] = normalized_categories

    markets = converted_match.get("markets")
    if isinstance(markets, list) and markets and not converted_match.get("subCategories"):
        converted_match["subCategories"] = [{"markets": markets}]

    return {"match": converted_match}


def decode_betclic_odds(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        if isinstance(value, int) and value > 1_000_000_000_000:
            try:
                return float(struct.unpack("d", struct.pack("<q", value))[0])
            except (struct.error, OverflowError):
                return None
        if 1.0 <= float(value) <= 1000.0:
            return float(value)
    return None


def _unwrap_selection_node(node: Any) -> dict[str, Any] | None:
    current = node
    for _ in range(4):
        if not isinstance(current, dict):
            return None
        if any(key in current for key in ("10", "11", "12", "name", "odds")):
            return current
        nested = current.get("1")
        if isinstance(nested, dict):
            current = nested
            continue
        return current
    return current if isinstance(current, dict) else None


def _normalize_grpc_selection(node: Any) -> dict[str, Any] | None:
    selection = _unwrap_selection_node(node)
    if not selection:
        return None
    label = str(
        selection.get("name")
        or selection.get("10")
        or selection.get("11")
        or selection.get("betslipName")
        or selection.get("3")
        or ""
    ).strip()
    if not label:
        return None
    odds = selection.get("odds")
    if odds is None:
        odds = decode_betclic_odds(selection.get("12"))
    if odds is None:
        odds = decode_betclic_odds(selection.get("6"))
    status = selection.get("status", selection.get("14", 1))
    return {
        "name": label,
        "betslipName": label,
        "odds": odds,
        "status": status,
        "betslipMarketId": str(selection.get("15", selection.get("1", ""))),
    }


def _normalize_grpc_market(node: Any) -> dict[str, Any] | None:
    if not isinstance(node, dict):
        return None
    label = str(
        node.get("betslipName")
        or node.get("3")
        or node.get("name")
        or node.get("2")
        or ""
    ).strip()
    if not label:
        return None

    selections_raw = node.get("mainSelections")
    if selections_raw is None:
        container = node.get("10")
        if isinstance(container, dict):
            selections_raw = container.get("1") or container.get("mainSelections")
        elif isinstance(container, list):
            selections_raw = container

    outcomes: list[dict[str, Any]] = []
    if isinstance(selections_raw, list):
        for item in selections_raw:
            normalized = _normalize_grpc_selection(item)
            if normalized and normalized.get("odds") is not None:
                outcomes.append(normalized)

    if not outcomes:
        return None
    return {
        "id": str(node.get("id", node.get("1", ""))),
        "name": str(node.get("name", node.get("2", label))),
        "betslipName": label,
        "mainSelections": outcomes,
    }


def _normalize_grpc_subcategory(node: Any) -> dict[str, Any] | None:
    if not isinstance(node, dict):
        return None
    markets_raw = node.get("markets")
    if markets_raw is None and isinstance(node.get("3"), list):
        markets_raw = node.get("3")
    markets: list[dict[str, Any]] = []
    if isinstance(markets_raw, list):
        for item in markets_raw:
            market = _normalize_grpc_market(item)
            if market:
                markets.append(market)
    if not markets:
        return None
    return {
        "id": str(node.get("id", node.get("1", ""))),
        "name": str(node.get("name", node.get("2", ""))),
        "markets": markets,
    }


def _normalize_grpc_category(node: Any) -> dict[str, Any] | None:
    if not isinstance(node, dict):
        return None
    category_id = str(node.get("id", node.get("2", node.get("1", "")))).strip()
    name = str(node.get("name", node.get("3", node.get("betslipName", "")))).strip()
    if not category_id and not name:
        return None
    return {"id": category_id, "name": name}


def _convert_protobuf_node(node: Any) -> Any:
    if isinstance(node, bytes):
        return node.decode("utf-8", errors="replace")
    if isinstance(node, list):
        return [_convert_protobuf_node(item) for item in node]
    if not isinstance(node, dict):
        return node

    converted: dict[str, Any] = {}
    for key, value in node.items():
        str_key = str(key)
        converted_value = _convert_protobuf_node(value)
        converted[str_key] = converted_value

    if "betslipName" not in converted and isinstance(converted.get("3"), str):
        converted["betslipName"] = converted["3"]
    if "name" not in converted and isinstance(converted.get("2"), str) and "mainSelections" in converted:
        converted["name"] = converted["2"]
    if "mainSelections" not in converted and isinstance(converted.get("10"), (list, dict)):
        container = converted.get("10")
        if isinstance(container, dict):
            converted["mainSelections"] = container.get("1") or container.get("mainSelections") or []
        else:
            converted["mainSelections"] = container
    if "mainSelections" in converted:
        selections = []
        for selection in converted["mainSelections"]:
            normalized = _normalize_grpc_selection(selection)
            if normalized:
                selections.append(normalized)
        if selections:
            converted["mainSelections"] = selections
    if "contestants" not in converted and isinstance(converted.get("9"), (list, dict)):
        converted["contestants"] = _convert_protobuf_node(converted["9"])
    if "matchId" not in converted and converted.get("1") is not None and not converted.get("mainSelections"):
        converted["matchId"] = str(converted["1"])
    if "openMarketCount" not in converted and isinstance(converted.get("7"), (int, float)):
        converted["openMarketCount"] = int(converted["7"])

    if "markets" not in converted and isinstance(converted.get("3"), list):
        markets = [_normalize_grpc_market(item) for item in converted["3"]]
        converted["markets"] = [item for item in markets if item]
    if "subCategories" not in converted and isinstance(converted.get("11"), (list, dict)):
        raw_sub = _convert_protobuf_node(converted["11"])
        if isinstance(raw_sub, dict):
            raw_sub = list(raw_sub.values())
        if isinstance(raw_sub, list):
            sub_categories = [_normalize_grpc_subcategory(item) for item in raw_sub]
            converted["subCategories"] = [item for item in sub_categories if item]
    if "categories" not in converted and isinstance(converted.get("10"), (list, dict)):
        raw_categories = _convert_protobuf_node(converted["10"])
        if isinstance(raw_categories, dict):
            raw_categories = list(raw_categories.values())
        if isinstance(raw_categories, list):
            categories = [_normalize_grpc_category(item) for item in raw_categories]
            converted["categories"] = [item for item in categories if item]

    return converted


def dump_frame_strings(frame_body: bytes, min_len: int = 4) -> list[str]:
    strings: list[str] = []
    current = bytearray()
    for byte in frame_body:
        if 32 <= byte < 127:
            current.append(byte)
        else:
            if len(current) >= min_len:
                strings.append(current.decode("ascii"))
            current = bytearray()
    if len(current) >= min_len:
        strings.append(current.decode("ascii"))
    return strings
