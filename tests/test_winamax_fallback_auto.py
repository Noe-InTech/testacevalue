import os

import winamax_fallback as wf


def test_builtin_fallback_when_eu_runner_has_secret(monkeypatch):
    monkeypatch.delenv("WINAMAX_FALLBACK_URL", raising=False)
    monkeypatch.delenv("WINAMAX_FALLBACK_URLS", raising=False)
    monkeypatch.setenv("RUNNER_ROLE", "eu")
    monkeypatch.setenv("RUNNER_SECRET", "test-secret")
    bases = wf.fallback_base_urls()
    assert wf.BUILTIN_EU_FALLBACK_BASES[0] in bases
    assert wf.winamax_fallback_enabled() is True


def test_fallback_tries_second_url_after_first_fails(monkeypatch):
    monkeypatch.setenv("RUNNER_ROLE", "eu")
    monkeypatch.setenv("RUNNER_SECRET", "s")
    monkeypatch.setenv("WINAMAX_FALLBACK_URLS", "https://bad.example,https://good.example")
    wf._LAST_GOOD_BASE = None
    calls: list[str] = []

    def fake_get(base, secret, path, *, params):
        calls.append(base)
        if "good" in base:
            return {"matches": {"1": {}}}
        return None

    monkeypatch.setattr(wf, "_get_fallback_json_from_base", fake_get)
    payload = wf.fetch_sport_payload_via_fallback(2)
    assert payload is not None
    assert "https://good.example" in calls
    assert wf._LAST_GOOD_BASE == "https://good.example"


def test_extra_urls_file(monkeypatch, tmp_path):
    monkeypatch.setenv("RUNNER_ROLE", "eu")
    monkeypatch.setenv("RUNNER_SECRET", "s")
    monkeypatch.delenv("WINAMAX_FALLBACK_URLS", raising=False)
    monkeypatch.delenv("WINAMAX_FALLBACK_URL", raising=False)
    path = tmp_path / "urls.txt"
    path.write_text("# comment\nhttps://file-relay.example\n", encoding="utf-8")
    monkeypatch.setenv("WINAMAX_FALLBACK_URLS_FILE", str(path))
    monkeypatch.setenv("WINAMAX_DISABLE_BUILTIN_FALLBACK", "1")
    bases = wf.fallback_base_urls()
    assert "https://file-relay.example" in bases


def test_eu_runner_defaults_to_relay(monkeypatch):
    monkeypatch.setenv("RUNNER_ROLE", "eu")
    monkeypatch.setenv("RUNNER_SECRET", "s")
    monkeypatch.setattr("winamax_fallback.winamax_fallback_enabled", lambda: True)
    monkeypatch.setattr("winamax_client.is_winamax_datacenter_feed_blocked", lambda **_: False)
    from winamax_client import _winamax_use_vercel_fallback

    assert _winamax_use_vercel_fallback() is True
