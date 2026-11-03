from winamax_client import WinamaxClient


def test_fetch_route_match_uses_fallback_when_blocked(monkeypatch):
    sample = {"bets": {"1": {"matchId": "99", "available": True}}, "outcomes": {}, "odds": {}}

    monkeypatch.setattr("winamax_client._winamax_use_vercel_fallback", lambda: True)
    monkeypatch.setattr(
        "winamax_fallback.fetch_route_payload_via_fallback",
        lambda route: sample if route == "match:99" else None,
    )

    payload = WinamaxClient().fetch_route("match:99")
    assert payload is sample
