from basketball_match_odds import build_basketball_match_odds_snapshot


def test_build_match_odds_winamax_and_fanduel() -> None:
    home = "Detroit Pistons"
    away = "Philadelphia 76ers"
    fanduel = {
        "markets": [
            {
                "marketName": "Moneyline",
                "runners": [
                    {"runnerName": home, "runnerStatus": "ACTIVE", "winRunnerOdds": {"trueOdds": {"decimalOdds": {"decimalOdds": 1.8}}}},
                    {"runnerName": away, "runnerStatus": "ACTIVE", "winRunnerOdds": {"trueOdds": {"decimalOdds": {"decimalOdds": 2.0}}}},
                ],
            },
            {
                "marketName": "Spread",
                "runners": [
                    {"runnerName": home, "handicap": -1.5, "runnerStatus": "ACTIVE", "winRunnerOdds": {"trueOdds": {"decimalOdds": {"decimalOdds": 1.9}}}},
                    {"runnerName": away, "handicap": 1.5, "runnerStatus": "ACTIVE", "winRunnerOdds": {"trueOdds": {"decimalOdds": {"decimalOdds": 1.9}}}},
                ],
            },
            {
                "marketName": "Total Points",
                "runners": [
                    {"runnerName": "Over", "handicap": 218.5, "runnerStatus": "ACTIVE", "winRunnerOdds": {"trueOdds": {"decimalOdds": {"decimalOdds": 1.91}}}},
                    {"runnerName": "Under", "handicap": 218.5, "runnerStatus": "ACTIVE", "winRunnerOdds": {"trueOdds": {"decimalOdds": {"decimalOdds": 1.91}}}},
                ],
            },
        ]
    }
    winamax = {
        "markets": [
            {"label": "Vainqueur", "outcomes": [(home, 1.62), (away, 1.82)]},
            {
                "label": "Écart de points (handicap)",
                "outcomes": [(f"{home} -1.5", 1.95), (f"{away} +1.5", 1.85)],
            },
            {
                "label": "Nombre de points (218.5)",
                "outcomes": [("Plus de 218,5", 1.68), ("Moins de 218,5", 1.78)],
            },
        ]
    }
    snap = build_basketball_match_odds_snapshot(
        match=f"{home} vs {away}",
        home=home,
        away=away,
        book_events={"winamax": winamax},
        fanduel_event=fanduel,
    )
    assert len(snap["books"]) == 2
    fd = snap["books"][0]
    assert fd["book"] == "fanduel"
    assert fd["moneyline_home"] is not None
    wx = snap["books"][1]
    assert wx["book"] == "winamax"
    assert wx["total_line"] == "218,5"
    assert wx["spread_line"] == "-1,5"
