"""Clés canoniques et alignement joueuses WNBA (FR ↔ FanDuel)."""

from __future__ import annotations

import re
import unicodedata
from typing import Any, Iterator

from tennis_market_mapping import format_numeric_line


def strip_accents(value: str) -> str:
    return (
        unicodedata.normalize("NFKD", value)
        .encode("ascii", "ignore")
        .decode("ascii")
        .lower()
    )


_GENERATIONAL_SUFFIXES = frozenset({"jr", "sr", "ii", "iii", "iv", "v"})


def _collapse_leading_initials(parts: list[str]) -> list[str]:
    """« P. J. Washington » et « PJ Washington » deviennent [pj, washington]."""
    if len(parts) < 3:
        return parts
    index = 0
    while index < len(parts) and len(parts[index]) == 1:
        index += 1
    if index >= 2 and index < len(parts):
        return ["".join(parts[:index]), *parts[index:]]
    return parts


def _name_parts(name: str) -> list[str]:
    text = strip_accents(name).replace("'", "").replace("’", "")
    raw = [part for part in re.split(r"[^a-z0-9]+", text) if part]
    return _collapse_leading_initials(raw)


def _identity(name: str) -> tuple[list[str], tuple[str, ...]]:
    """Prénom(s) + nom, et le suffixe Jr/Sr/II à part.

    Le suffixe reste dans l'identité : « Gary Trent » n'est pas « Gary Trent Jr ».
    Il n'est pas le nom de famille : « Jones Jr » n'est pas « Acuff Jr ».
    """
    parts = _name_parts(name)
    suffixes: list[str] = []
    while len(parts) > 1 and parts[-1] in _GENERATIONAL_SUFFIXES:
        suffixes.append(parts[-1])
        parts = parts[:-1]
    suffixes.reverse()
    return parts, tuple(suffixes)


def _core_name_parts(name: str) -> list[str]:
    core, _suffix = _identity(name)
    return core


def _opens_with_initial(name: str) -> bool:
    core, _suffix = _identity(name)
    return len(core) >= 2 and len(core[0]) == 1


def basketball_players_match(name_a: str, name_b: str) -> bool:
    """Même joueur seulement si prénom, nom et suffixe collent.

    Un nom de famille seul, un « Jr » partagé, ou le même prénom ne suffit pas.
    Une initiale (« J. Holiday », « A. Wilson ») ne colle que si elle préfixe
    le prénom et que le reste du nom est identique.
    """
    core_a, suffix_a = _identity(name_a)
    core_b, suffix_b = _identity(name_b)
    if not core_a or not core_b or suffix_a != suffix_b:
        return False
    if core_a == core_b:
        return True
    if core_a[-1] != core_b[-1]:
        return False
    if len(core_a) == 1 or len(core_b) == 1:
        return False
    if core_a[1:] != core_b[1:]:
        return False
    first_a, first_b = core_a[0], core_b[0]
    if first_a == first_b:
        return True
    if len(first_a) == 1 and len(first_b) > 1 and first_b.startswith(first_a):
        return True
    if len(first_b) == 1 and len(first_a) > 1 and first_a.startswith(first_b):
        return True
    return False


def player_identity_token(name: str) -> str:
    """Clé stable, indépendante du reste du roster.

    « Derrick Jones Jr. » et « Darius Acuff Jr. » ne partagent plus « jr ».
    """
    parts = _name_parts(name)
    if not parts:
        return "player"
    return "".join(parts)


def player_token(name: str) -> str:
    """Nom de famille, suffixe générationnel ignoré."""
    parts = _core_name_parts(name)
    if not parts:
        return "player"
    return parts[-1]


def build_player_compare_tokens(roster: list[str]) -> dict[str, str]:
    """Une clé par graphie. Elle ne dépend pas des autres joueurs du roster."""
    result: dict[str, str] = {}
    for raw_name in roster:
        name = str(raw_name or "").strip()
        if name:
            result[name] = player_identity_token(name)
    return result


def player_compare_token(name: str, roster: list[str] | None = None) -> str:
    """Clé du joueur. Un nom complet ne change pas selon le roster.

    Le roster ne sert qu'à développer une initiale unique (« A. Wilson »).
    """
    text = str(name or "").strip()
    if not text:
        return "player"
    if roster and _opens_with_initial(text):
        resolved = resolve_roster_player(text, roster)
        if resolved != text and basketball_players_match(text, resolved):
            text = resolved
    return player_identity_token(text)


def fanduel_market_names_other_player(label: str, player_name: str) -> bool:
    """True si le libellé FanDuel nomme un autre joueur que la ligne FR."""
    text = str(label or "").strip()
    named_player = str(player_name or "").strip()
    if not text or not named_player or " - " not in text:
        return False
    lower = strip_accents(text)
    if lower.startswith("to score") or lower.startswith("to record"):
        return False
    head = text.split(" - ", 1)[0].strip()
    if not head:
        return False
    return not basketball_players_match(named_player, head)


def is_player_prop_family(family: str) -> bool:
    return family in {
        "points_player",
        "rebounds_player",
        "assists_player",
        "threes_made_player",
        "blocks_player",
        "steals_player",
        "turnovers_player",
        "points_rebounds_player",
        "points_assists_player",
        "rebounds_assists_player",
        "pra_player",
        "double_double_player",
        "steals_blocks_player",
    }


def is_comparable_player_prop_key(compare_key: str) -> bool:
    family = compare_key.split("|", 1)[0]
    return is_player_prop_family(family)


def parse_player_prop_key(compare_key: str) -> tuple[str, str, float | None]:
    parts = compare_key.split("|")
    family = parts[0] if parts else ""
    token = parts[1] if len(parts) >= 2 else ""
    line: float | None = None
    if len(parts) >= 3:
        try:
            line = float(parts[2])
        except ValueError:
            line = None
    return family, token, line


def build_player_prop_key(
    family: str,
    player_name: str,
    line: str | float,
    *,
    roster: list[str] | None = None,
) -> str:
    return f"{family}|{player_compare_token(player_name, roster)}|{format_numeric_line(line)}"


def build_player_tier_prop_key(
    family: str,
    player_name: str,
    threshold: int | str,
    *,
    roster: list[str] | None = None,
) -> str:
    """Paliers type Unibet « 4+ » / FanDuel « To Record 4+ » (pas une ligne O/U 3,5)."""
    tier = int(threshold)
    return f"{family}|{player_compare_token(player_name, roster)}|+{tier}"


def is_tier_prop_line(line: str | float | None) -> bool:
    return str(line or "").strip().startswith("+")


def tier_prop_line_threshold(line: str | float | None) -> int | None:
    text = str(line or "").strip()
    if not text.startswith("+"):
        return None
    try:
        return int(text[1:])
    except ValueError:
        return None


def build_double_double_key(
    player_name: str,
    *,
    roster: list[str] | None = None,
) -> str:
    return f"double_double_player|{player_compare_token(player_name, roster)}|0"


def tier_threshold_to_ou_line(threshold: int | str) -> str:
    return format_numeric_line(float(threshold) - 0.5)


def compare_key_line_suffix(compare_key: str) -> str:
    parts = compare_key.split("|")
    return parts[2] if len(parts) >= 3 else ""


def resolve_fanduel_match_for_fr_prop(
    compare_key: str,
    outcome: str,
    fd_map: dict[str, dict[str, Any]],
) -> tuple[dict[str, Any], str, str] | None:
    """Lie une issue FR à FanDuel.

    Paliers Unibet « N+ » → priorité à l'alt O/U FD « Over (N-0,5) » (ex. 4+ ↔ 3,5),
    puis repli sur « To Record N+ » si l'alt n'existe pas.
    """
    tier = tier_prop_line_threshold(compare_key_line_suffix(compare_key))
    if tier is not None:
        parts = compare_key.split("|")
        if len(parts) < 3:
            return None
        family, token = parts[0], parts[1]
        ou_key = f"{family}|{token}|{tier_threshold_to_ou_line(tier)}"
        fd_ou = fd_map.get(ou_key)
        if fd_ou:
            bundle = fd_ou.get("outcomes", {}).get("Over")
            if bundle is not None and bundle.get("decimal_fr") is not None:
                return fd_ou, "Over", ou_key
        fd_tier = fd_map.get(compare_key)
        if fd_tier:
            fd_outcome = "Over" if outcome in {"Over", "Yes"} else outcome
            bundle = fd_tier.get("outcomes", {}).get(fd_outcome)
            if bundle is not None and bundle.get("decimal_fr") is not None:
                return fd_tier, fd_outcome, compare_key
        return None

    fd_market = fd_map.get(compare_key)
    if not fd_market:
        return None
    fd_outcome = outcome
    bundle = fd_market.get("outcomes", {}).get(fd_outcome)
    if bundle is None or bundle.get("decimal_fr") is None:
        return None
    return fd_market, fd_outcome, compare_key


def align_fr_outcome_to_fanduel(outcome: str, compare_key: str) -> str:
    family = compare_key.split("|", 1)[0]
    if not is_player_prop_family(family):
        return outcome
    if family == "double_double_player":
        return "Yes"
    lower = strip_accents(outcome)
    if lower in {"over", "under"}:
        return outcome.capitalize()
    if lower.startswith("plus"):
        return "Over"
    if lower.startswith("moins"):
        return "Under"
    if lower in {"oui", "yes"}:
        return "Yes"
    return outcome


# Rétrocompat tests / imports intermédiaires
align_fr_outcome_to_pinnacle = align_fr_outcome_to_fanduel


FD_PLAYER_PROP_SPECS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("points_player", re.compile(r"^(.+?)\s*-\s*points$", re.I)),
    ("rebounds_player", re.compile(r"^(.+?)\s*-\s*rebounds$", re.I)),
    ("assists_player", re.compile(r"^(.+?)\s*-\s*assists$", re.I)),
    ("threes_made_player", re.compile(r"^(.+?)\s*-\s*made\s*threes$", re.I)),
    ("blocks_player", re.compile(r"^(.+?)\s*-\s*blocks$", re.I)),
    ("steals_player", re.compile(r"^(.+?)\s*-\s*steals$", re.I)),
    ("turnovers_player", re.compile(r"^(.+?)\s*-\s*turnovers$", re.I)),
    ("points_rebounds_player", re.compile(r"^(.+?)\s*-\s*pts\s*\+\s*reb$", re.I)),
    ("points_assists_player", re.compile(r"^(.+?)\s*-\s*pts\s*\+\s*ast$", re.I)),
    ("rebounds_assists_player", re.compile(r"^(.+?)\s*-\s*reb\s*\+\s*ast$", re.I)),
    ("pra_player", re.compile(r"^(.+?)\s*-\s*pts\s*\+\s*reb\s*\+\s*ast$", re.I)),
)

FD_ALT_PLAYER_PROP_SPECS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("points_player", re.compile(r"^(.+?)\s*-\s*alt points$", re.I)),
    ("rebounds_player", re.compile(r"^(.+?)\s*-\s*alt rebounds$", re.I)),
    ("assists_player", re.compile(r"^(.+?)\s*-\s*alt assists$", re.I)),
    ("points_rebounds_player", re.compile(r"^(.+?)\s*-\s*alt pts \+ reb$", re.I)),
    ("points_assists_player", re.compile(r"^(.+?)\s*-\s*alt pts \+ ast$", re.I)),
    ("rebounds_assists_player", re.compile(r"^(.+?)\s*-\s*alt reb \+ ast$", re.I)),
    ("pra_player", re.compile(r"^(.+?)\s*-\s*alt pts \+ reb \+ ast$", re.I)),
)

FD_TIER_MARKET_SPECS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("points_player", re.compile(r"^to score (\d+)\+ points$", re.I)),
    ("rebounds_player", re.compile(r"^to record (\d+)\+ rebounds$", re.I)),
    ("assists_player", re.compile(r"^to record (\d+)\+ assists$", re.I)),
    ("threes_made_player", re.compile(r"^to record (\d+)\+ made threes$", re.I)),
    ("blocks_player", re.compile(r"^to record (\d+)\+ blocks$", re.I)),
    ("steals_player", re.compile(r"^to record (\d+)\+ steals$", re.I)),
)


def is_full_game_fanduel_prop_market(market_name: str) -> bool:
    lower = strip_accents(str(market_name or ""))
    if not lower:
        return False
    period_markers = (
        "quarter",
        "qtr",
        "1st",
        "2nd",
        "3rd",
        "4th",
        "mi-temps",
        "half",
        "period",
    )
    return not any(marker in lower for marker in period_markers)


def is_fanduel_ou_player_prop_market_name(market_name: str) -> bool:
    name = str(market_name or "").strip()
    lower = strip_accents(name)
    if not lower or lower.startswith("to score") or lower.startswith("to record"):
        return False
    if "1st qtr" in lower or "quarter" in lower:
        return False
    return any(spec[1].search(name) for spec in FD_PLAYER_PROP_SPECS)


def extract_fanduel_player_prop_line(market: dict[str, Any]) -> str | None:
    for runner in market.get("runners", []):
        handicap = runner.get("handicap")
        if handicap is not None:
            return format_numeric_line(handicap)
        match = re.search(r"([\d.]+)\s*$", str(runner.get("runnerName", "")))
        if match:
            return format_numeric_line(match.group(1))
    return None


def resolve_roster_player(player_name: str, roster: list[str] | None) -> str:
    """Resout un libelle vers un nom roster. Ne choisit pas au hasard si homonymes."""
    text = str(player_name or "").strip()
    if not text or not roster:
        return text
    exact = [
        candidate
        for candidate in roster
        if strip_accents(text) == strip_accents(str(candidate).strip())
    ]
    if len(exact) == 1:
        return exact[0]
    fuzzy_matches = [
        str(candidate).strip()
        for candidate in roster
        if basketball_players_match(text, candidate)
    ]
    # Dedup accents
    seen: set[str] = set()
    unique_fuzzy: list[str] = []
    for candidate in fuzzy_matches:
        key = strip_accents(candidate)
        if key in seen:
            continue
        seen.add(key)
        unique_fuzzy.append(candidate)
    if len(unique_fuzzy) == 1:
        return unique_fuzzy[0]
    if len(unique_fuzzy) > 1:
        text_parts = [part for part in re.split(r"[\s.]+", strip_accents(text)) if part]
        if text_parts:
            first = text_parts[0]
            hinted = [
                candidate
                for candidate in unique_fuzzy
                if first == strip_accents(candidate).split()[0]
                or (
                    len(first) == 1
                    and strip_accents(candidate).split()
                    and strip_accents(candidate).split()[0].startswith(first)
                )
                or first in strip_accents(candidate).split()
            ]
            if len(hinted) == 1:
                return hinted[0]
        # Ambigu : ne pas coller la premiere joueuse trouvee.
        return text
    return text


def map_fanduel_market_to_compare_key(
    market: dict[str, Any],
    *,
    roster: list[str] | None = None,
) -> str | None:
    name = str(market.get("marketName", "")).strip()
    if not is_fanduel_ou_player_prop_market_name(name):
        return None
    line = extract_fanduel_player_prop_line(market)
    if not line:
        return None
    for family, pattern in FD_PLAYER_PROP_SPECS:
        match = pattern.search(name)
        if not match:
            continue
        player_name = resolve_roster_player(match.group(1).strip(), roster)
        return build_player_prop_key(family, player_name, line, roster=roster)
    return None


def parse_fanduel_alt_runner(
    runner_name: str,
    *,
    roster: list[str] | None = None,
) -> tuple[str, str, str] | None:
    """Parse « Joueur Over 12.5 » sur marchés FanDuel Alt."""
    match = re.match(r"(.+?)\s+(Over|Under)\s+([\d.]+)\s*$", str(runner_name or "").strip(), re.I)
    if not match:
        return None
    player_name = resolve_roster_player(match.group(1).strip(), roster)
    line = format_numeric_line(match.group(3))
    outcome = match.group(2).capitalize()
    return player_name, line, outcome


def fanduel_player_prop_runner_outcome(runner_name: str) -> str:
    lower = runner_name.strip().lower()
    if lower.endswith(" over") or lower.startswith("over"):
        return "Over"
    if lower.endswith(" under") or lower.startswith("under"):
        return "Under"
    return runner_name.strip()


def iter_fanduel_player_prop_slots(
    market: dict[str, Any],
    *,
    roster: list[str] | None = None,
) -> Iterator[tuple[str, str]]:
    """Yield (compare_key, outcome) for each runner FanDuel d'un marché props joueuse."""
    name = str(market.get("marketName", "")).strip()
    lower = strip_accents(name)

    compare_key = map_fanduel_market_to_compare_key(market, roster=roster)
    if compare_key:
        for runner in market.get("runners", []):
            if runner.get("runnerStatus") not in (None, "ACTIVE"):
                continue
            runner_name = str(runner.get("runnerName", "")).strip()
            yield compare_key, fanduel_player_prop_runner_outcome(runner_name)
        return

    if lower == "to record a double double":
        for runner in market.get("runners", []):
            if runner.get("runnerStatus") not in (None, "ACTIVE"):
                continue
            player_name = resolve_roster_player(str(runner.get("runnerName", "")).strip(), roster)
            yield build_double_double_key(player_name, roster=roster), "Yes"
        return

    for family, pattern in FD_TIER_MARKET_SPECS:
        match = pattern.search(name)
        if not match:
            continue
        if not is_full_game_fanduel_prop_market(name):
            continue
        threshold = int(match.group(1))
        for runner in market.get("runners", []):
            if runner.get("runnerStatus") not in (None, "ACTIVE"):
                continue
            player_name = resolve_roster_player(str(runner.get("runnerName", "")).strip(), roster)
            yield build_player_tier_prop_key(family, player_name, threshold, roster=roster), "Over"
        return
