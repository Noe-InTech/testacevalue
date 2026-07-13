"""Assemblage et comparaison progressive d'un anchor basketball (WNBA / NBA)."""

from __future__ import annotations

from typing import Any, Callable

from fanduel_client import format_american_moneyline, format_french_decimal

PartialCallback = Callable[[dict[str, Any], str], None]


def assemble_anchor_result(
    anchor: dict[str, Any],
    *,
    book_events: dict[str, dict[str, Any]],
    roster: list[str],
    fr_map: dict[str, dict[str, Any]],
    fd_map: dict[str, dict[str, Any]],
    fr_scraped_at: str | None,
    fd_scraped_at: str | None,
    compare_normalized_props: Callable[..., list[dict[str, Any]]],
    enrich_fr_only_row: Callable[[dict[str, Any]], dict[str, Any]],
    enrich_fd_only_row: Callable[[dict[str, Any]], dict[str, Any]],
    attach_capture_times: Callable[..., list[dict[str, Any]]],
) -> dict[str, Any]:
    comparable = compare_normalized_props(fr_map, fd_map)

    fr_only: list[dict[str, Any]] = []
    for compare_key, fr_market in fr_map.items():
        fd_market = fd_map.get(compare_key)
        for outcome, fr_payload in fr_market["outcomes"].items():
            if fd_market and outcome in fd_market.get("outcomes", {}):
                continue
            fr_only.append(
                enrich_fr_only_row(
                    {
                        "compare_key": compare_key,
                        "market_family": fr_market["market_family"],
                        "player_name": fr_market.get("player_name", ""),
                        "outcome": outcome,
                        "best_fr_odds": fr_payload["odds"],
                        "best_fr_bookmaker": fr_payload["bookmaker_label"],
                        "fr_market_label": fr_market["market_label_raw"],
                    }
                )
            )

    fd_only: list[dict[str, Any]] = []
    for compare_key, fd_market in fd_map.items():
        fr_market = fr_map.get(compare_key)
        for outcome, fd_bundle in fd_market.get("outcomes", {}).items():
            if fr_market and outcome in fr_market.get("outcomes", {}):
                continue
            fd_only.append(
                enrich_fd_only_row(
                    {
                        "compare_key": compare_key,
                        "market_family": fd_market.get("market_family", compare_key.split("|", 1)[0]),
                        "player_name": "",
                        "outcome": outcome,
                        "fanduel_market_label": fd_market.get("market_label", ""),
                        "cote_fr_fanduel": format_french_decimal(float(fd_bundle["decimal_fr"])),
                        "cote_us_fanduel_ml": format_american_moneyline(fd_bundle.get("american")),
                    }
                )
            )

    attach_capture_times(comparable, fr_scraped_at=fr_scraped_at, fd_scraped_at=fd_scraped_at)
    attach_capture_times(fr_only, fr_scraped_at=fr_scraped_at)
    attach_capture_times(fd_only, fd_scraped_at=fd_scraped_at)

    return {
        "match": anchor["match"],
        "sources": sorted(anchor["sources"]),
        "fanduel_event_id": anchor.get("fanduel_event_id"),
        "comparable_count": len(comparable),
        "fr_only_count": len(fr_only),
        "fd_only_count": len(fd_only),
        "fr_prop_market_count": len(fr_map),
        "fd_prop_market_count": len(fd_map),
        "comparables": comparable,
        "fr_only": fr_only,
        "fd_only": fd_only,
    }


def flush_anchor_partial(
    anchor: dict[str, Any],
    *,
    book_events: dict[str, dict[str, Any]],
    roster: list[str],
    fr_map: dict[str, dict[str, Any]],
    fd_map: dict[str, dict[str, Any]],
    fr_scraped_at: str | None,
    fd_scraped_at: str | None,
    step: str,
    on_partial: PartialCallback | None,
    compare_normalized_props: Callable[..., list[dict[str, Any]]],
    enrich_fr_only_row: Callable[[dict[str, Any]], dict[str, Any]],
    enrich_fd_only_row: Callable[[dict[str, Any]], dict[str, Any]],
    attach_capture_times: Callable[..., list[dict[str, Any]]],
) -> None:
    if on_partial is None:
        return
    snapshot = assemble_anchor_result(
        anchor,
        book_events=book_events,
        roster=roster,
        fr_map=fr_map,
        fd_map=fd_map,
        fr_scraped_at=fr_scraped_at,
        fd_scraped_at=fd_scraped_at,
        compare_normalized_props=compare_normalized_props,
        enrich_fr_only_row=enrich_fr_only_row,
        enrich_fd_only_row=enrich_fd_only_row,
        attach_capture_times=attach_capture_times,
    )
    on_partial(snapshot, step)
