"""Probe rapide du SSR Betclic tennis."""

from __future__ import annotations

from betclic_client import BetclicClient


def main() -> None:
    client = BetclicClient()
    competitions = client.list_tennis_competitions()
    print(f"competitions={len(competitions)}")
    for item in competitions[:30]:
        print(
            f"- {item.country_code} | {item.competition_name} "
            f"(id={item.competition_id})"
        )


if __name__ == "__main__":
    main()
