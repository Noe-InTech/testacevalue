from compare_tennis_aces_vs_fanduel import format_ligne_aces_fr


def test_format_ligne_aces_player_over() -> None:
    assert (
        format_ligne_aces_fr(
            {
                "compare_key": "aces_player|zverev|14.5",
                "outcome": "Over",
            }
        )
        == "Plus de 14,5 aces — Zverev"
    )


def test_format_ligne_aces_player_under() -> None:
    assert (
        format_ligne_aces_fr(
            {
                "compare_key": "aces_player|fery|5.5",
                "outcome": "Under",
            }
        )
        == "Moins de 5,5 aces — Fery"
    )


def test_format_ligne_aces_total_match() -> None:
    assert (
        format_ligne_aces_fr(
            {
                "compare_key": "aces_total|9.5",
                "outcome": "Over",
            }
        )
        == "Plus de 9,5 aces — match"
    )


def test_format_ligne_aces_fallback_marche() -> None:
    assert (
        format_ligne_aces_fr(
            {
                "compare_key": "aces_total_tiers",
                "outcome": "Over",
                "fr_market_label": "Nombre d'aces (palier)",
            }
        )
        == "Plus — Nombre d'aces (palier)"
    )
