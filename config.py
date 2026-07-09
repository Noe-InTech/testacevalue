import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")


@dataclass(frozen=True)
class Config:
    api_key: str
    bookmakers: list[str]
    sports: list[str]
    poll_interval: int
    min_ev_percent: float

    @classmethod
    def from_env(cls) -> "Config":
        api_key = os.getenv("ODDS_API_KEY", "")
        if not api_key:
            raise ValueError("ODDS_API_KEY manquante dans .env")

        return cls(
            api_key=api_key,
            bookmakers=_split_csv(os.getenv("BOOKMAKERS", "pinnacle,winamax_fr")),
            sports=_split_csv(
                os.getenv(
                    "SPORTS",
                    "soccer_france_ligue_one,soccer_epl,soccer_uefa_champs_league,soccer_fifa_world_cup",
                )
            ),
            poll_interval=int(os.getenv("POLL_INTERVAL", "600")),
            min_ev_percent=float(os.getenv("MIN_EV_PERCENT", "3.0")),
        )


def _split_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]
