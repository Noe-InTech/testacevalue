"""Relance automatiquement la comparaison Coteur vs Pinnacle jusqu'au succès."""

import argparse
import json
import logging
import time
from pathlib import Path

from compare_markets import OUTPUT_DIR, run

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("resume_compare")


def load_partial_flag(path: Path) -> bool:
    with path.open("r", encoding="utf-8") as f:
        payload = json.load(f)
    return bool(payload.get("partial", False))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Relance compare_markets.py jusqu'a ce que le quota permette un export complet."
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=OUTPUT_DIR / "market_compare_latest.json",
        help="Fichier JSON de sortie stable, ecrase a chaque tentative",
    )
    parser.add_argument(
        "--interval-minutes",
        type=float,
        default=30.0,
        help="Delai entre deux tentatives si le quota est insuffisant",
    )
    parser.add_argument(
        "--max-attempts",
        type=int,
        default=0,
        help="Nombre max de tentatives. 0 = illimite",
    )
    args = parser.parse_args()

    attempt = 0
    while True:
        attempt += 1
        log.info("Tentative %d", attempt)
        output_path = run(args.output)
        if not load_partial_flag(output_path):
            log.info("Export complet disponible: %s", output_path.resolve())
            return 0

        if args.max_attempts and attempt >= args.max_attempts:
            log.warning("Maximum de tentatives atteint, dernier export partiel conserve.")
            return 1

        sleep_seconds = max(args.interval_minutes, 0) * 60
        log.info(
            "Quota insuffisant, nouvelle tentative dans %.1f minute(s).",
            args.interval_minutes,
        )
        time.sleep(sleep_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
