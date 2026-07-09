"""Write web/public/run_status.json for the Vercel dashboard."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

STATUS_PATH = Path(__file__).resolve().parent.parent / "web" / "public" / "run_status.json"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--status", required=True, choices=("running", "success", "error"))
    parser.add_argument("--message", default="")
    parser.add_argument("--match", default="")
    parser.add_argument("--from-json")
    args = parser.parse_args()

    payload: dict[str, object] = {
        "status": args.status,
        "message": args.message,
        "match_filter": args.match,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    if args.from_json:
        source = Path(args.from_json)
        if source.is_file():
            data = json.loads(source.read_text(encoding="utf-8"))
            payload["generated_at"] = data.get("generated_at", "")
            payload["comparable_count"] = data.get("comparable_count", 0)
            payload["fr_higher_count"] = data.get("fr_higher_count", 0)

    STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATUS_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
