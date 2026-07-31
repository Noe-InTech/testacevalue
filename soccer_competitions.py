"""Liste rapide des compétitions foot (pour filtre UI)."""

from __future__ import annotations

from collections import Counter
from typing import Any

from fanduel_soccer_client import FanDuelSoccerClient, split_soccer_teams
from soccer_constants import FANDUEL_SOCCER_EVENT_TYPE_ID


def list_soccer_competitions() -> list[dict[str, Any]]:
    """Compétitions FanDuel actuelles + nb de matchs visibles sur la page SPORT."""
    client = FanDuelSoccerClient()
    try:
        payload = client._get(
            "/api/content-managed-page",
            {"page": "SPORT", "eventTypeId": FANDUEL_SOCCER_EVENT_TYPE_ID},
        )
    except RuntimeError:
        return []

    attachments = payload.get("attachments") or {}
    competitions = attachments.get("competitions") or {}
    events = attachments.get("events") or {}

    counts: Counter[str] = Counter()
    for event in events.values():
        if not isinstance(event, dict):
            continue
        name = str(event.get("name") or "")
        home, away = split_soccer_teams(name)
        if not home or not away:
            continue
        cid = str(event.get("competitionId") or "")
        if cid:
            counts[cid] += 1

    rows: list[dict[str, Any]] = []
    for cid, meta in competitions.items():
        if not isinstance(meta, dict):
            continue
        label = str(meta.get("name") or "").strip()
        if not label:
            continue
        rows.append(
            {
                "id": str(cid),
                "name": label,
                "event_count": int(counts.get(str(cid), 0)),
                "source": "fanduel",
            }
        )

    # Si un event n'a pas de competition dans le dict (rare), ignorer.
    rows.sort(key=lambda row: (-int(row["event_count"]), str(row["name"]).lower()))
    return rows
