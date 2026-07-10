from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class ValueBet:
  sport: str
  event: str
  commence_time: str
  market: str
  outcome: str
  soft_book: str
  soft_odds: float
  sharp_odds: float
  fair_prob: float
  ev_percent: float


def implied_probability(decimal_odds: float) -> float:
  if decimal_odds <= 1.0:
    return 0.0
  return 1.0 / decimal_odds


def outcome_key(outcome: dict[str, Any]) -> str:
  parts = [outcome.get("name", "")]
  if "point" in outcome:
    parts.append(str(outcome["point"]))
  if outcome.get("description"):
    parts.append(outcome["description"])
  return " | ".join(parts)


def outcome_label(outcome: dict[str, Any]) -> str:
  key = outcome_key(outcome)
  return key.replace(" | ", " ")


def remove_vig_multiplicative(odds: dict[str, float]) -> dict[str, float]:
  probs = {name: implied_probability(price) for name, price in odds.items()}
  total = sum(probs.values())
  if total <= 0:
    return {name: 0.0 for name in odds}
  return {name: prob / total for name, prob in probs.items()}


def _group_outcomes_by_line(outcomes: list[dict[str, Any]]) -> list[dict[str, dict[str, Any]]]:
  groups: dict[str, dict[str, dict[str, Any]]] = {}

  for outcome in outcomes:
    line = str(outcome.get("point", "_"))
    groups.setdefault(line, {})[outcome_key(outcome)] = outcome

  return list(groups.values())


def fair_probabilities(sharp_outcomes: list[dict[str, Any]]) -> dict[str, float]:
  fair: dict[str, float] = {}

  for group in _group_outcomes_by_line(sharp_outcomes):
    keys = list(group.keys())
    if len(keys) == 1:
      fair[keys[0]] = implied_probability(float(group[keys[0]]["price"]))
      continue

    odds = {key: float(group[key]["price"]) for key in keys}
    fair.update(remove_vig_multiplicative(odds))

  return fair


def find_value_bets_in_event(
  event: dict[str, Any],
  sport: str,
  sharp_book: str,
  soft_books: list[str],
  min_ev_percent: float,
) -> list[ValueBet]:
  values: list[ValueBet] = []
  bookmakers = {bm["key"]: bm for bm in event.get("bookmakers", [])}
  sharp = bookmakers.get(sharp_book)
  if not sharp:
    return values

  event_label = f"{event['home_team']} vs {event['away_team']}"
  commence_time = event.get("commence_time", "")

  for market in sharp.get("markets", []):
    market_key = market["key"]
    sharp_outcomes = market.get("outcomes", [])
    if not sharp_outcomes:
      continue

    sharp_odds = {outcome_key(o): float(o["price"]) for o in sharp_outcomes}
    fair_probs = fair_probabilities(sharp_outcomes)

    for soft_key in soft_books:
      soft_bm = bookmakers.get(soft_key)
      if not soft_bm:
        continue

      soft_market = next(
        (m for m in soft_bm.get("markets", []) if m["key"] == market_key),
        None,
      )
      if not soft_market:
        continue

      for outcome in soft_market.get("outcomes", []):
        key = outcome_key(outcome)
        soft_price = float(outcome["price"])
        fair_prob = fair_probs.get(key)
        sharp_price = sharp_odds.get(key)

        if not fair_prob or not sharp_price:
          continue

        ev_percent = (fair_prob * soft_price - 1.0) * 100
        if ev_percent < min_ev_percent:
          continue

        values.append(
          ValueBet(
            sport=sport,
            event=event_label,
            commence_time=commence_time,
            market=market_key,
            outcome=outcome_label(outcome),
            soft_book=soft_key,
            soft_odds=soft_price,
            sharp_odds=sharp_price,
            fair_prob=fair_prob,
            ev_percent=ev_percent,
          )
        )

  return values


def find_value_bets(
  events: list[dict[str, Any]],
  sport: str,
  sharp_book: str,
  soft_books: list[str],
  min_ev_percent: float,
) -> list[ValueBet]:
  values: list[ValueBet] = []

  for event in events:
    values.extend(
      find_value_bets_in_event(event, sport, sharp_book, soft_books, min_ev_percent)
    )

  values.sort(key=lambda v: v.ev_percent, reverse=True)
  return values
