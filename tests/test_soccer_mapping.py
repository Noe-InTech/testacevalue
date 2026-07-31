"""Tests mapping foot (tirs match/équipe, corners, Winamax assists)."""

from __future__ import annotations

from soccer_books_mapping import normalize_fr_soccer_market
from soccer_market_mapping import classify_fr_market_label, map_fanduel_soccer_market


def test_classify_fr_core_labels():
    assert classify_fr_market_label("Buteur") == "anytime_goalscorer"
    assert classify_fr_market_label("Joueur décisif") == "score_or_assist"
    assert classify_fr_market_label("Nombre de passes décisives") == "anytime_assist"
    assert classify_fr_market_label("Remplaçant buteur") is None


def test_winamax_assist_plus_outcomes():
    items = normalize_fr_soccer_market(
        "Nombre de passes décisives",
        [("Nicolas Fernandez Mercau 1+", 3.5), ("Nicolas Fernandez Mercau 2+", 15.0)],
        ["Nicolas Fernandez Mercau"],
    )
    keys = {i.compare_key for i in items}
    assert any(k.endswith("|yes") for k in keys)
    assert any("|2+" in k for k in keys)


def test_fanduel_match_and_team_shots():
    mapped = map_fanduel_soccer_market(
        {
            "marketName": "Match Shots",
            "runners": [{"runnerName": "20 Or More Shots"}],
        },
        roster=[],
        home_team="New York City",
        away_team="Toronto FC",
    )
    assert mapped[0][0] == "shots_match|match|20+"
    assert mapped[0][3] == "Yes"

    mapped = map_fanduel_soccer_market(
        {
            "marketName": "Team To Have 12 Or More Shots",
            "runners": [{"runnerName": "New York City"}, {"runnerName": "Toronto FC"}],
        },
        roster=[],
        home_team="New York City",
        away_team="Toronto FC",
    )
    keys = {row[0] for row in mapped}
    assert "shots_team|city|12+" in keys
    assert "shots_team|toronto|12+" in keys or "shots_team|fc|12+" in keys


def test_fanduel_corners_ou():
    mapped = map_fanduel_soccer_market(
        {
            "marketName": "Total Corners 8.5",
            "runners": [
                {"runnerName": "Over 8.5 Corners"},
                {"runnerName": "Under 8.5 Corners"},
            ],
        },
        roster=[],
    )
    assert {row[3] for row in mapped} == {"Over", "Under"}
    assert all(row[0].startswith("corners_match|match|") for row in mapped)
