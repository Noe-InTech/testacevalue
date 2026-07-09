import argparse
import logging
import time
from datetime import datetime, timezone

from api_client import OddsApiClient
from config import Config
from markets import collect_allowed_markets
from value_engine import ValueBet, find_value_bets_in_event

logging.basicConfig(
  level=logging.INFO,
  format="%(asctime)s [%(levelname)s] %(message)s",
  datefmt="%H:%M:%S",
)
log = logging.getLogger("valuebot")

SHARP_BOOK = "pinnacle"


def format_value(v: ValueBet) -> str:
  return (
    f"  +{v.ev_percent:.1f}% EV | [{v.market}] {v.outcome} @ {v.soft_odds:.2f} ({v.soft_book}) "
    f"| Pinnacle: {v.sharp_odds:.2f} | fair: {v.fair_prob:.1%}"
  )


def scan_sport(
  client: OddsApiClient,
  sport: str,
  bookmakers: list[str],
  min_ev_percent: float,
) -> list[ValueBet]:
  values: list[ValueBet] = []
  soft_books = [b for b in bookmakers if b != SHARP_BOOK]

  try:
    events = client.get_events(sport)
  except RuntimeError as e:
    log.warning("Erreur %s : %s", sport, e)
    return values

  if not events:
    log.info("%s : aucun match à venir", sport)
    return values

  log.info("%s : %d match(s) à analyser", sport, len(events))

  for event in events:
    event_label = f"{event['home_team']} vs {event['away_team']}"

    try:
      markets_resp = client.get_event_markets(sport, event["id"], [SHARP_BOOK])
      allowed = collect_allowed_markets(markets_resp, SHARP_BOOK)
    except RuntimeError as e:
      log.warning("  %s : impossible de lister les marchés (%s)", event_label, e)
      continue

    if not allowed:
      log.debug("  %s : aucun marché autorisé", event_label)
      continue

    try:
      event_odds = client.get_event_odds(sport, event["id"], bookmakers, allowed)
    except RuntimeError as e:
      log.warning("  %s : impossible de récupérer les cotes (%s)", event_label, e)
      continue

    returned_markets = {
      m["key"]
      for bm in event_odds.get("bookmakers", [])
      for m in bm.get("markets", [])
    }

    if not returned_markets:
      continue

    event_values = find_value_bets_in_event(
      event_odds, sport, SHARP_BOOK, soft_books, min_ev_percent
    )
    values.extend(event_values)

    log.info(
      "  %s : %d marché(s) comparé(s), %d value(s)",
      event_label,
      len(returned_markets),
      len(event_values),
    )

  values.sort(key=lambda v: v.ev_percent, reverse=True)
  return values


def scan_once(client: OddsApiClient, config: Config) -> list[ValueBet]:
  all_values: list[ValueBet] = []

  for sport in config.sports:
    all_values.extend(
      scan_sport(client, sport, config.bookmakers, config.min_ev_percent)
    )

  quota = client.last_quota
  if quota.remaining is not None:
    log.info(
      "Crédits : %d restants | %d utilisés | dernier appel : %d",
      quota.remaining,
      quota.used or 0,
      quota.last_cost or 0,
    )

  return all_values


def display_values(values: list[ValueBet], min_ev: float) -> None:
  if not values:
    log.info("Aucune value bet détectée (seuil : +%.1f%%)", min_ev)
    return

  log.info("=== %d VALUE BET(S) DÉTECTÉE(S) ===", len(values))
  current_event = ""
  for v in values:
    if v.event != current_event:
      current_event = v.event
      log.info("")
      log.info("[%s] %s — %s", v.sport, v.event, v.commence_time)
    log.info(format_value(v))


def run(once: bool = False) -> None:
  config = Config.from_env()
  client = OddsApiClient(config.api_key)

  log.info("Value Bet Bot démarré")
  log.info("Sports : %s", ", ".join(config.sports))
  log.info("Bookmakers : %s", ", ".join(config.bookmakers))
  log.info("Marchés : tous sauf handicaps et scores exacts")
  log.info("Seuil EV : +%.1f%% | Poll : %ds", config.min_ev_percent, config.poll_interval)

  sports = client.get_sports()
  active = [s["title"] for s in sports if s.get("active")]
  log.info("API OK — %d sports actifs", len(active))

  while True:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    log.info("--- Scan %s ---", now)

    values = scan_once(client, config)
    display_values(values, config.min_ev_percent)

    if once:
      break

    log.info("Prochain scan dans %d secondes...", config.poll_interval)
    time.sleep(config.poll_interval)


if __name__ == "__main__":
  parser = argparse.ArgumentParser(description="Value Bet Bot")
  parser.add_argument("--once", action="store_true", help="Un seul scan puis quitter")
  args = parser.parse_args()
  run(once=args.once)
