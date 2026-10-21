"""Profile build_best_fr_player_props_map on live listings (runner EU)."""

from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from betclic_basketball_client import BetclicBasketballClient
from basketball_books_mapping import BOOK_NORMALIZERS, is_wnba_player_prop_label
from compare_wnba_props_vs_fanduel import (
    build_best_fr_player_props_map,
    discover_anchors,
    fetch_live_nba_listings,
    merge_roster,
    resolve_basketball_book_link,
)
from fanduel_basketball_client import FanDuelBasketballClient
from unibet_basketball_client import UnibetBasketballClient
from winamax_basketball_client import WinamaxBasketballClient


def _time_unibet_markets(u_payload: dict, roster: list[str]) -> None:
    normalizer = BOOK_NORMALIZERS["unibet"]
    for market in u_payload.get("markets") or []:
        label = str(market.get("label", "")).strip()
        if not is_wnba_player_prop_label(label):
            continue
        outcomes = [(str(raw), odds) for raw, odds in market.get("outcomes", [])]
        t0 = time.perf_counter()
        items = list(normalizer(label, outcomes, roster))
        elapsed = time.perf_counter() - t0
        if elapsed > 0.5 or len(outcomes) > 80:
            print(
                f"SLOW unibet market {elapsed:.2f}s "
                f"outcomes={len(outcomes)} norm={len(items)} label={label[:70]!r}"
            )


def main() -> None:
    u = UnibetBasketballClient()
    b = BetclicBasketballClient()
    w = WinamaxBasketballClient(fetch_timeout=10)
    f = FanDuelBasketballClient()
    print("fetch listings...", flush=True)
    ue, bl, wl, fe, _ = fetch_live_nba_listings(
        unibet=u, betclic=b, winamax=w, fanduel=f, schedule_hours=48
    )
    anchors = discover_anchors(
        unibet_events=ue, betclic_links=bl, winamax_links=wl, fanduel_events=fe
    )
    if not anchors:
        print("no anchors")
        return
    anchor = anchors[0]
    print("anchor", anchor["match"], flush=True)
    wl_link = resolve_basketball_book_link(
        anchor, wl, match_id_key="winamax_match_id", source_key="winamax"
    )
    ue_ev = resolve_basketball_book_link(
        anchor,
        ue,
        match_id_key="unibet_event_id",
        source_key="unibet",
        id_attr="event_id",
    )
    print("scrape winamax...", flush=True)
    w_payload = w.build_event_payload(wl_link)
    prop_labels = sum(
        1
        for m in w_payload["markets"]
        if is_wnba_player_prop_label(str(m.get("label", "")))
    )
    print(
        "winamax markets",
        len(w_payload["markets"]),
        "prop-like labels",
        prop_labels,
        flush=True,
    )
    book_events = {"winamax": w_payload}
    roster = merge_roster(
        w_payload.get("roster"),
        [],
        [],
        [anchor["home_team"], anchor["away_team"]],
    )
    t0 = time.perf_counter()
    fr = build_best_fr_player_props_map(book_events, roster=roster)
    print("winamax only fr keys", len(fr), "sec", round(time.perf_counter() - t0, 2), flush=True)

    print("scrape unibet...", flush=True)
    u_payload = u.build_event_payload(ue_ev)
    print("unibet markets", len(u_payload["markets"]), flush=True)
    _time_unibet_markets(u_payload, roster)
    book_events["unibet"] = u_payload
    roster = merge_roster(
        w_payload.get("roster"),
        u_payload.get("roster"),
        [],
        [anchor["home_team"], anchor["away_team"]],
    )
    print("build winamax+unibet map...", flush=True)
    t0 = time.perf_counter()
    fr = build_best_fr_player_props_map(book_events, roster=roster)
    print("winamax+unibet fr keys", len(fr), "sec", round(time.perf_counter() - t0, 2), flush=True)


if __name__ == "__main__":
    main()
