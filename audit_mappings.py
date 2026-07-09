"""Audit Coteur outcome mappings vs Pinnacle across all WC matches."""

from collections import defaultdict

from compare_markets import (
    build_pinnacle_variant_map,
    display_team,
    match_coteur_to_pinnacle_event,
    normalize_team,
)
from coteur_client import CoteurClient
from market_mapping import coteur_outcome_label, map_coteur_to_pinnacle
from pinnacle_guest_client import PinnacleGuestClient
from scrape_pinnacle import build_event_payload, is_main_event

CANDIDATES = {
    "HT": [
        {"1": "home", "2": "away", "3": "draw"},
        {"1": "home", "2": "draw", "3": "away"},
    ],
    "OU": [
        {"2": "over", "3": "under"},
        {"2": "under", "3": "over"},
    ],
    "HTOU": [
        {"2": "over", "3": "under"},
        {"2": "under", "3": "over"},
    ],
    "BTTS": [
        {"1": "yes", "2": "no"},
        {"1": "no", "2": "yes"},
    ],
    "DC": [
        {"1": "1x", "2": "2x", "3": "12"},
        {"1": "2x", "2": "1x", "3": "12"},
    ],
    "HTDC": [
        {"1": "1x", "2": "2x", "3": "12"},
        {"1": "2x", "2": "1x", "3": "12"},
    ],
    "DNB": [
        {"1": "home", "2": "away"},
        {"1": "away", "2": "home"},
    ],
    "1n2": [
        {"0": "draw", "1": "home", "2": "away"},
    ],
    "TOQ": [
        {"1": "home", "2": "away"},
        {"1": "away", "2": "home"},
    ],
}

PINNACLE_OUTCOME_MAP = {
    "home": lambda home, away: home,
    "away": lambda home, away: away,
    "draw": lambda home, away: "Nul",
    "over": lambda home, away: "Over",
    "under": lambda home, away: "Under",
    "yes": lambda home, away: "Oui",
    "no": lambda home, away: "Non",
    "1x": lambda home, away: f"{home} ou Nul",
    "2x": lambda home, away: f"{away} ou Nul",
    "12": lambda home, away: f"{home} ou {away}",
}


def median_odds(values: list[float]) -> float | None:
    vals = sorted(values)
    if not vals:
        return None
    mid = len(vals) // 2
    if len(vals) % 2:
        return vals[mid]
    return (vals[mid - 1] + vals[mid]) / 2


def rel_err(actual: float, expected: float) -> float:
    if expected == 0:
        return 999.0
    return abs(actual - expected) / expected


def find_pinnacle_odds(pout: dict[str, float], label: str, kind: str, home: str, away: str) -> float | None:
    if label in pout:
        return pout[label]
    if kind in ("home", "away"):
        target = normalize_team(home if kind == "home" else away)
        for outcome_label, odds in pout.items():
            if normalize_team(outcome_label) == target or target in normalize_team(outcome_label):
                return odds
    return None


def main() -> None:
    coteur = CoteurClient()
    pinnacle = PinnacleGuestClient()
    league = pinnacle.find_world_cup_league()
    pinnacle_events = [
        build_event_payload(pinnacle, matchup)
        for matchup in pinnacle.get_league_matchups(league.id)
        if is_main_event(matchup)
    ]

    scores: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    samples: dict[str, list[tuple]] = defaultdict(list)

    for match in coteur.list_world_cup_matches():
        data = coteur.get_full_odds(match["renc_id"])
        pinnacle_event = match_coteur_to_pinnacle_event(data, pinnacle_events)
        if not pinnacle_event:
            continue

        info = data.get("info") or {}
        home = display_team((info.get("teamDom") or {}).get("equipeNom", ""))
        away = display_team((info.get("teamExt") or {}).get("equipeNom", ""))
        pinnacle_variants = build_pinnacle_variant_map(pinnacle_event)

        for entry in data.get("odds", []):
            typename = entry.get("typename", "")
            special = entry.get("special") or ""
            pinnacle_key = map_coteur_to_pinnacle(typename, special)
            if not pinnacle_key or pinnacle_key not in pinnacle_variants:
                continue

            market_data = coteur.get_market_odds(match["renc_id"], typename, special)
            code_odds: dict[str, list[float]] = defaultdict(list)
            for value in market_data.get("values", []):
                if value.get("disable"):
                    continue
                for code, odds in (value.get("current") or {}).items():
                    if odds:
                        code_odds[str(code)].append(float(odds))
            if not code_odds:
                continue

            pinnacle_outcomes = {
                outcome["label"]: outcome["odds"]
                for outcome in pinnacle_variants[pinnacle_key]["outcomes"]
            }

            if typename in CANDIDATES:
                for candidate in CANDIDATES[typename]:
                    key = str(candidate)
                    matched = 0
                    total_err = 0.0
                    for code, odds_list in code_odds.items():
                        kind = candidate.get(code)
                        if not kind:
                            continue
                        label = PINNACLE_OUTCOME_MAP[kind](home, away)
                        pinnacle_odd = find_pinnacle_odds(pinnacle_outcomes, label, kind, home, away)
                        median = median_odds(odds_list)
                        if pinnacle_odd and median and rel_err(median, pinnacle_odd) < 0.25:
                            matched += 1
                            total_err += rel_err(median, pinnacle_odd)
                    if matched:
                        scores[typename][key] += matched - total_err
                        samples[typename].append(
                            (
                                f"{home} vs {away}",
                                pinnacle_key,
                                candidate,
                                matched,
                                total_err / matched,
                            )
                        )
            else:
                matched = 0
                total_err = 0.0
                for code, odds_list in code_odds.items():
                    label = coteur_outcome_label(typename, code, home, away)
                    pinnacle_odd = find_pinnacle_odds(pinnacle_outcomes, label, "", home, away)
                    median = median_odds(odds_list)
                    if pinnacle_odd and median and rel_err(median, pinnacle_odd) < 0.25:
                        matched += 1
                        total_err += rel_err(median, pinnacle_odd)
                if matched:
                    scores[typename]["current"] += matched - total_err

    print("=== BEST MAPPING PER MARKET TYPE ===")
    for typename in sorted(scores):
        best_key, best_score = max(scores[typename].items(), key=lambda item: item[1])
        print(f"\n{typename}: score={best_score:.2f}")
        print(f"  best: {best_key}")
        if typename in CANDIDATES:
            for sample in samples[typename]:
                if str(sample[2]) == best_key:
                    print(
                        f"  {sample[0]} {sample[1]} "
                        f"matched={sample[3]} avg_err={sample[4]:.3f}"
                    )

    print("\n=== CURRENT FIXED MAPPINGS ===")
    for typename, mapping_scores in sorted(scores.items()):
        if typename in CANDIDATES:
            continue
        print(f"{typename}: score={mapping_scores.get('current', 0):.2f}")


if __name__ == "__main__":
    main()
