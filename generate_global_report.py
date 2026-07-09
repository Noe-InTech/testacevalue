"""Genere un rapport global tests + pipeline tennis books."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

OUTPUT_DIR = Path(__file__).parent / "output"


def run_unit_tests() -> tuple[int, int, str]:
    proc = subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py", "-v"],
        capture_output=True,
        text=True,
        cwd=Path(__file__).parent,
    )
    output = proc.stdout + proc.stderr
    passed = output.count(" ... ok")
    failed = output.count(" ... FAIL") + output.count(" ... ERROR")
    if proc.returncode == 0 and "Ran " in output:
        return passed, failed, output
    return passed, failed, output


def load_compare(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def collect_best_book_stats(payload: dict[str, Any]) -> Counter[str]:
    stats: Counter[str] = Counter()
    for result in payload.get("results", []):
        for market in result.get("comparable_markets", []):
            for outcome in market.get("outcomes_compared", []):
                stats[outcome.get("best_bookmaker", "")] += 1
    return stats


def collect_top_edges(payload: dict[str, Any], limit: int = 15) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for result in payload.get("results", []):
        event = result.get("event_display_fr") or result.get("event", "")
        for market in result.get("comparable_markets", []):
            for outcome in market.get("outcomes_compared", []):
                unibet = float(outcome.get("unibet_odds", 0.0))
                for book in ("betclic", "winamax"):
                    book_odds = outcome.get(f"{book}_odds")
                    if book_odds is None:
                        continue
                    delta = float(book_odds) - unibet
                    rows.append(
                        {
                            "event": event,
                            "compare_key": market.get("compare_key", ""),
                            "is_advanced": market.get("is_advanced", False),
                            "outcome": outcome.get("outcome", ""),
                            "unibet_odds": unibet,
                            "book": book,
                            "book_odds": float(book_odds),
                            "delta": delta,
                            "abs_delta": abs(delta),
                            "best": outcome.get("best_bookmaker", ""),
                        }
                    )
    rows.sort(key=lambda row: row["abs_delta"], reverse=True)
    return rows[:limit]


def summarize_advanced(payload: dict[str, Any]) -> list[dict[str, Any]]:
    summary = []
    for result in payload.get("results", []):
        advanced_markets = [
            market
            for market in result.get("comparable_markets", [])
            if market.get("is_advanced")
        ]
        by_family = Counter(market.get("market_family", "") for market in advanced_markets)
        winamax_advanced = sum(
            1 for market in advanced_markets if "winamax" in market.get("books_compared", [])
        )
        summary.append(
            {
                "event": result.get("event_display_fr", ""),
                "advanced_comparable": len(advanced_markets),
                "winamax_advanced": winamax_advanced,
                "unibet_only_advanced": sum(
                    1 for item in result.get("unibet_only_markets", []) if item.get("is_advanced")
                ),
                "families": dict(by_family),
            }
        )
    return summary


def collect_fr_fanduel_top_edges(payload: dict[str, Any], limit: int = 20) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for result in payload.get("results", []):
        event = result.get("event_display_fr") or result.get("event", "")
        for market in result.get("comparable_markets", []):
            for outcome in market.get("outcomes_compared", []):
                if outcome.get("best_side") != "fr":
                    continue
                rows.append(
                    {
                        "event": event,
                        "compare_key": market.get("compare_key", ""),
                        "is_advanced": market.get("is_advanced", False),
                        "outcome": outcome.get("outcome", ""),
                        "best_fr_odds": float(outcome.get("best_fr_odds", 0.0)),
                        "best_fr_bookmaker": outcome.get("best_fr_bookmaker", ""),
                        "fanduel_odds": float(outcome.get("fanduel_odds", 0.0)),
                        "price_delta": float(outcome.get("price_delta", 0.0)),
                    }
                )
    rows.sort(key=lambda row: row["price_delta"], reverse=True)
    return rows[:limit]


def build_markdown(
    *,
    test_passed: int,
    test_failed: int,
    test_output: str,
    compare_path: Path,
    payload: dict[str, Any],
    fr_fanduel_path: Path | None = None,
    fr_fanduel_payload: dict[str, Any] | None = None,
) -> str:
    generated = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    best_stats = collect_best_book_stats(payload)
    top_edges = collect_top_edges(payload)
    advanced_summary = summarize_advanced(payload)

    total_comparable = sum(result.get("comparable_market_count", 0) for result in payload.get("results", []))
    total_advanced = sum(result.get("advanced_comparable_count", 0) for result in payload.get("results", []))
    total_winamax_advanced = sum(
        result.get("winamax_advanced_comparable_count", 0) for result in payload.get("results", [])
    )

    lines = [
        "# Rapport global — Pipeline tennis FR",
        "",
        f"Genere le : **{generated}**",
        "",
        "## 1. Tests unitaires",
        "",
        f"- Resultat : **{'OK' if test_failed == 0 else 'ECHEC'}**",
        f"- Tests passes : **{test_passed}**",
        f"- Tests en echec : **{test_failed}**",
        "",
        "<details>",
        "<summary>Log unittest</summary>",
        "",
        "```",
        test_output.strip()[-4000:],
        "```",
        "",
        "</details>",
        "",
        "## 2. Pipeline live (Unibet / Betclic / Winamax)",
        "",
        f"- Source JSON : `{compare_path.name}`",
        f"- Matchs Unibet (simples) : **{payload.get('unibet_event_count', 0)}**",
        f"- Matchs Betclic scrapes : **{payload.get('betclic_event_count', 0)}**",
        f"- Matchs Winamax (Socket.IO) : **{payload.get('winamax_event_count', 0)}**",
        f"- Matchs compares : **{payload.get('matched_count', 0)}**",
        "",
    ]

    unmatched_betclic = payload.get("unmatched_unibet_betclic", [])
    unmatched_winamax = payload.get("unmatched_unibet_winamax", [])
    if unmatched_betclic:
        lines.append(f"- Sans correspondance Betclic : {', '.join(unmatched_betclic)}")
    if unmatched_winamax:
        lines.append(f"- Sans correspondance Winamax : {', '.join(unmatched_winamax)}")
    lines.append("")

    lines.extend(
        [
            "### Synthese comparables",
            "",
            f"- Total marches comparables : **{total_comparable}**",
            f"- Dont marches avances : **{total_advanced}**",
            f"- Avances avec Winamax : **{total_winamax_advanced}**",
            "",
            "### Par match",
            "",
            "| Match | Unibet | Betclic SSR/total | Winamax | Comparables | Avances | Avances+Winamax |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )

    for result in payload.get("results", []):
        lines.append(
            f"| {result.get('event_display_fr', '')} | "
            f"{result.get('unibet_market_count', 0)} | "
            f"{result.get('betclic_ssr_market_count', 0)}/{result.get('betclic_open_market_count', 0)} | "
            f"{result.get('winamax_market_count', 0)} | "
            f"{result.get('comparable_market_count', 0)} | "
            f"{result.get('advanced_comparable_count', 0)} | "
            f"{result.get('winamax_advanced_comparable_count', 0)} |"
        )

    lines.extend(["", "### Marches avances comparables", ""])
    for item in advanced_summary:
        families = ", ".join(f"{name} ({count})" for name, count in sorted(item["families"].items()))
        lines.append(
            f"- **{item['event']}** : {item['advanced_comparable']} comparables "
            f"({item['winamax_advanced']} avec Winamax), "
            f"{item['unibet_only_advanced']} avances Unibet seul — {families or 'n/a'}"
        )

    lines.extend(
        [
            "",
            "### Meilleur bookmaker (issues comparables)",
            "",
            "| Bookmaker | Issues gagnantes |",
            "| --- | ---: |",
        ]
    )
    for book, count in best_stats.most_common():
        if book:
            lines.append(f"| {book} | {count} |")

    lines.extend(
        [
            "",
            "### Top ecarts de cotes vs Unibet",
            "",
            "| Match | Marche | Issue | Unibet | Book | Cote | Ecart | Meilleur |",
            "| --- | --- | --- | ---: | --- | ---: | ---: | --- |",
        ]
    )
    for row in top_edges:
        adv = " *" if row["is_advanced"] else ""
        lines.append(
            f"| {row['event']} | `{row['compare_key']}`{adv} | {row['outcome']} | "
            f"{row['unibet_odds']:.3f} | {row['book']} | {row['book_odds']:.3f} | "
            f"{row['delta']:+.3f} | {row['best']} |"
        )

    lines.extend(
        [
            "",
            "## 3. Etat des integrations",
            "",
            "| Bookmaker | Methode | Marches de base | Marches avances | Statut |",
            "| --- | --- | --- | --- | --- |",
            "| Unibet | SSR HTML + live | h2h, jeux, sets | breaks, aces, tie-breaks | OK |",
            "| Betclic | SSR + gRPC-web | h2h, jeux, sets | breaks, aces (ca_ten_ptss) | OK |",
            "| Winamax | Socket.IO | h2h, jeux, sets | breaks, tie-breaks, 1er break | OK |",
            "",
            "## 4. Best FR vs FanDuel",
            "",
        ]
    )

    if fr_fanduel_payload and fr_fanduel_path:
        fr_edges = collect_fr_fanduel_top_edges(fr_fanduel_payload)
        total_fr_higher = sum(result.get("fr_higher_than_fanduel_count", 0) for result in fr_fanduel_payload.get("results", []))
        lines.extend(
            [
                f"- Source JSON : `{fr_fanduel_path.name}`",
                f"- Matchs compares : **{fr_fanduel_payload.get('matched_count', 0)}**",
                f"- Issues ou la meilleure cote FR bat FanDuel : **{total_fr_higher}**",
                "",
                "### Top edges FR > FanDuel",
                "",
                "| Match | Marche | Issue | Best FR | Book | FanDuel | Ecart |",
                "| --- | --- | --- | ---: | --- | ---: | ---: |",
            ]
        )
        for row in fr_edges:
            adv = " *" if row["is_advanced"] else ""
            lines.append(
                f"| {row['event']} | `{row['compare_key']}`{adv} | {row['outcome']} | "
                f"{row['best_fr_odds']:.3f} | {row['best_fr_bookmaker']} | "
                f"{row['fanduel_odds']:.3f} | {row['price_delta']:+.3f} |"
            )
        lines.append("")
    else:
        lines.extend(["- Pipeline non execute dans ce rapport.", ""])

    lines.extend(
        [
            "## 5. Fichiers generes",
            "",
            f"- `{compare_path.name}`",
            f"- `{compare_path.with_suffix('.csv').name}`",
        ]
    )
    if fr_fanduel_path:
        lines.extend([f"- `{fr_fanduel_path.name}`", f"- `{fr_fanduel_path.with_suffix('.csv').name}`"])
    lines.extend(
        [
            f"- `tennis_books_diff_{compare_path.stem.replace('tennis_books_compare_', '')}.md`",
            f"- `unibet_advanced_gaps_{compare_path.stem.replace('tennis_books_compare_', '')}.md`",
            "",
            "## 6. Points d'attention",
            "",
            "- Betclic gRPC : debloque via headers `X-BG-*` + decode odds int64 ; ~45-48 marches vs 80-90 ouverts.",
            "- Winamax : pas de marches aces sur les matchs Wimbledon actuels ; breaks/tie-breaks OK.",
            "- Unibet live : matchs `/paris-en-direct/` inclus (ex. Muchova-Gauff).",
            "- Comparaison finale : `compare_tennis_fr_best_vs_fanduel.py` = max(Unibet,Betclic,Winamax) vs FanDuel.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Rapport global tests + pipeline tennis")
    parser.add_argument("--compare-json", type=Path, help="JSON compare_tennis_books")
    parser.add_argument("--fr-fanduel-json", type=Path, help="JSON compare_tennis_fr_best_vs_fanduel")
    parser.add_argument("--output", type=Path, help="Rapport markdown de sortie")
    parser.add_argument("--skip-tests", action="store_true")
    args = parser.parse_args()

    if args.compare_json:
        compare_path = args.compare_json
    else:
        candidates = sorted(OUTPUT_DIR.glob("tennis_books_compare_*.json"))
        if not candidates:
            raise SystemExit("Aucun fichier tennis_books_compare_*.json dans output/")
        compare_path = candidates[-1]

    if args.fr_fanduel_json:
        fr_fanduel_path = args.fr_fanduel_json
    else:
        fr_candidates = sorted(OUTPUT_DIR.glob("tennis_fr_best_vs_fanduel_*.json"))
        fr_fanduel_path = fr_candidates[-1] if fr_candidates else None

    if args.skip_tests:
        test_passed, test_failed, test_output = 0, 0, "(tests non executes)"
    else:
        test_passed, test_failed, test_output = run_unit_tests()

    payload = load_compare(compare_path)
    fr_fanduel_payload = load_compare(fr_fanduel_path) if fr_fanduel_path else None
    markdown = build_markdown(
        test_passed=test_passed,
        test_failed=test_failed,
        test_output=test_output,
        compare_path=compare_path,
        payload=payload,
        fr_fanduel_path=fr_fanduel_path,
        fr_fanduel_payload=fr_fanduel_payload,
    )

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = args.output or OUTPUT_DIR / f"global_report_{stamp}.md"
    report_path.write_text(markdown, encoding="utf-8")
    print(f"Rapport : {report_path}")
    print(f"Tests : {test_passed} OK, {test_failed} FAIL")
    print(f"Compare : {compare_path.name} ({payload.get('matched_count', 0)} matchs)")
    if fr_fanduel_path:
        print(f"FR vs FanDuel : {fr_fanduel_path.name}")
    return 1 if test_failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
