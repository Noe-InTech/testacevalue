import winamax_client
from winamax_client import is_winamax_datacenter_feed_blocked, _parse_preloaded_state

BLOCKED_HTML = """<!DOCTYPE html><html><body>
<script>
            var PRELOADED_STATE = {"cc":{},"notifications":{},"terms":{},"events":{},"browser":{}};

</script></body></html>"""

FULL_HTML = """<!DOCTYPE html><html><body>
<script>
            var PRELOADED_STATE = {"sportIds":[2],"sports":{"2":{}},"matches":{"1":{"sportId":2}}};

</script></body></html>"""


def test_parse_preloaded_state():
    state = _parse_preloaded_state(FULL_HTML)
    assert state is not None
    assert "matches" in state


def test_datacenter_blocked_detects_stripped_preload(monkeypatch):
    winamax_client._DATACENTER_BLOCK_CACHE = None
    class FakeResponse:
        text = BLOCKED_HTML

        def raise_for_status(self):
            return None

    class FakeSession:
        def get(self, *args, **kwargs):
            return FakeResponse()

    monkeypatch.setattr("winamax_client._new_winamax_session", lambda: FakeSession())
    assert is_winamax_datacenter_feed_blocked() is True


def test_datacenter_not_blocked_when_sports_present(monkeypatch):
    winamax_client._DATACENTER_BLOCK_CACHE = None

    class FakeResponse:
        text = FULL_HTML

        def raise_for_status(self):
            return None

    class FakeSession:
        def get(self, *args, **kwargs):
            return FakeResponse()

    monkeypatch.setattr("winamax_client._new_winamax_session", lambda: FakeSession())
    monkeypatch.setattr(
        "winamax_client._parse_preloaded_state",
        lambda _html: {"sportIds": [2], "sports": {"2": {}}},
    )
    assert is_winamax_datacenter_feed_blocked(refresh=True) is False
