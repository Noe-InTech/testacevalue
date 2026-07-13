"""Compare stats joueurs NBA — books FR vs FanDuel."""

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
    parser = argparse.ArgumentParser(description="Compare props NBA FR vs FanDuel")
    parser.add_argument("--match", default="", help="Filtre texte sur le match")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=OUTPUT_DIR / "nba_props_compare.json",
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
    args = parser.parse_args()

    if args.progress_json or args.status_json:
        run_live_compare(
            args.output,
            match_filter=args.match,
            progress_json=args.progress_json,
            status_json=args.status_json,
            league="nba",
        )
        return

    payload = run_compare(match_filter=args.match, league="nba")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    log.info(
        "NBA compare terminé — %d match(s), %d comparable(s), %d FR seul, %d FD seul",
        payload["matches_done"],
        payload["comparable_count"],
        payload["fr_only_count"],
        payload["fd_only_count"],
    )


if __name__ == "__main__":
    main()
