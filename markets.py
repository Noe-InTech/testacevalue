"""Filtre des marchés à comparer (exclut handicaps et scores exacts)."""


def is_allowed_market(market_key: str) -> bool:
  key = market_key.lower()

  if key.endswith("_lay"):
    return False
  if key.startswith("correct_score"):
    return False
  if "spread" in key:
    return False

  return True


def collect_allowed_markets(markets_response: dict, bookmaker: str = "pinnacle") -> list[str]:
  keys: set[str] = set()

  for bm in markets_response.get("bookmakers", []):
    if bm["key"] != bookmaker:
      continue
    for market in bm.get("markets", []):
      key = market.get("key", "")
      if is_allowed_market(key):
        keys.add(key)

  return sorted(keys)
