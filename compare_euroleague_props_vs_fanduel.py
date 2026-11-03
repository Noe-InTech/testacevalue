"""Compare stats joueurs Euroleague — books FR vs FanDuel."""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

from compare_wnba_props_vs_fanduel import OUTPUT_DIR, run_compare, run_live_compare

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare props Euroleague FR vs FanDuel")
    parser.add_argument("--match", default="", help="Filtre texte sur le match")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=OUTPUT_DIR / "euroleague_props_compare.json",
    )
    parser.add_argument(
        "--progress-json",
        type=Path,
        help="Ecrit les resultats partiels au fil de l'eau (JSON)",
    )
    parser.add_argument(
        "--status-json",
        type=Path,
        help="Met a jour le statut du run (JSON)",
    )
    parser.add_argument(
        "--hours",
        type=int,
        default=96,
        help="Fenetre Euroleague en heures (24, 48 ou 96 — defaut 96)",
    )
    args = parser.parse_args()

    if args.progress_json or args.status_json:
        run_live_compare(
            args.output,
            match_filter=args.match,
            progress_json=args.progress_json,
            status_json=args.status_json,
            league="euroleague",
            schedule_hours=args.hours,
        )
        return

    payload = run_compare(
        match_filter=args.match,
        league="euroleague",
        schedule_hours=args.hours,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    log.info(
        "Euroleague compare terminé — %d match(s), %d comparable(s), %d FR seul, %d FD seul",
        payload.get("anchors_total", 0),
        payload.get("comparable_count", 0),
        payload.get("fr_only_count", 0),
        payload.get("fd_only_count", 0),
    )


if __name__ == "__main__":
    main()
