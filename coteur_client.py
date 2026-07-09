"""Client pour l'API interne oddsv2.coteur.com."""

import base64
import hashlib
import os
import re
from datetime import datetime
from typing import Any

import requests
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad

COTEUR_ODDS_BASE = "https://oddsv2.coteur.com"
COTEUR_WEB_BASE = "https://www.coteur.com"
DEFAULT_FOOTBALL_COMPETITION_SEEDS = (
    f"{COTEUR_WEB_BASE}/cotes/foot",
)
DEFAULT_TENNIS_COMPETITION_SEEDS = (
    f"{COTEUR_WEB_BASE}/cotes/tennis/atp/wimbledon",
    f"{COTEUR_WEB_BASE}/cotes/tennis/wta/wimbledon",
    f"{COTEUR_WEB_BASE}/cotes/tennis/monde/wimbledon-simples-hommes",
    f"{COTEUR_WEB_BASE}/cotes/tennis/atp/wimbledon-simples-hommes",
    f"{COTEUR_WEB_BASE}/cotes/tennis/wta/wimbledon-simples-dames",
)


def _evp_bytes_to_key(password: bytes, salt: bytes, key_len: int, iv_len: int) -> tuple[bytes, bytes]:
    derived = b""
    block = b""
    while len(derived) < key_len + iv_len:
        block = hashlib.md5(block + password + salt).digest()
        derived += block
    return derived[:key_len], derived[key_len : key_len + iv_len]


def generate_token(password: str = "1231") -> str:
    """Token journalier (CryptoJS.AES.encrypt(date_fr, '1231'))."""
    date_fr = datetime.now().strftime("%d/%m/%Y")
    salt = os.urandom(8)
    key, iv = _evp_bytes_to_key(password.encode(), salt, 32, 16)
    cipher = AES.new(key, AES.MODE_CBC, iv)
    encrypted = cipher.encrypt(pad(date_fr.encode(), AES.block_size))
    return base64.b64encode(b"Salted__" + salt + encrypted).decode()


class CoteurClient:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "Accept": "application/json",
        })

    def _token_headers(self) -> dict[str, str]:
        return {"token": generate_token()}

    def get_full_odds(self, renc_id: int) -> dict[str, Any]:
        response = self.session.get(
            f"{COTEUR_ODDS_BASE}/odds/getFullOdds/{renc_id}",
            headers=self._token_headers(),
            timeout=30,
        )
        if response.status_code != 200:
            raise RuntimeError(f"Coteur API {response.status_code}: {response.text[:200]}")
        return response.json()

    def get_market_odds(self, renc_id: int, typename: str, special: str = "") -> dict[str, Any]:
        response = self.session.post(
            f"{COTEUR_ODDS_BASE}/odds/getOdds",
            headers={
                **self._token_headers(),
                "Content-Type": "application/json; charset=utf-8",
            },
            json={
                "rencId": renc_id,
                "typename": typename,
                "special": special,
            },
            timeout=30,
        )
        if response.status_code != 200:
            raise RuntimeError(
                f"Coteur market API {response.status_code}: {response.text[:200]}"
            )
        return response.json()

    def get_players(self, ids: list[str] | list[int]) -> list[dict[str, Any]]:
        response = self.session.post(
            f"{COTEUR_WEB_BASE}/api/renc/players",
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "X-Requested-With": "XMLHttpRequest",
            },
            data=[("ids[]", str(player_id)) for player_id in ids],
            timeout=30,
        )
        if response.status_code != 200:
            raise RuntimeError(
                f"Coteur players API {response.status_code}: {response.text[:200]}"
            )
        return response.json()

    def get_bookmakers(self) -> list[dict[str, Any]]:
        response = self.session.get(
            f"{COTEUR_WEB_BASE}/api/bookmakers/all",
            headers={"X-Requested-With": "XMLHttpRequest"},
            timeout=30,
        )
        if response.status_code != 200:
            raise RuntimeError(
                f"Coteur bookmakers API {response.status_code}: {response.text[:200]}"
            )
        return response.json()

    def list_matches_from_competition_page(self, competition_url: str) -> list[dict[str, Any]]:
        response = self.session.get(competition_url, timeout=30)
        if response.status_code != 200:
            raise RuntimeError(f"Page Coteur {response.status_code}")

        matches = []
        for slug, renc_id in re.findall(r'href="/cote/([^"]+)-(\d+)"', response.text):
            parts = slug.rsplit("-", 1)
            if len(parts) == 2:
                home_slug, away_slug = parts[0], parts[1]
            else:
                home_slug, away_slug = slug, ""

            matches.append({
                "renc_id": int(renc_id),
                "slug": slug,
                "home_slug": home_slug.replace("-", " "),
                "away_slug": away_slug.replace("-", " "),
                "url": f"{COTEUR_WEB_BASE}/cote/{slug}-{renc_id}",
            })

        seen: set[int] = set()
        unique = []
        for match in matches:
            if match["renc_id"] not in seen:
                seen.add(match["renc_id"])
                unique.append(match)
        return unique

    def list_world_cup_matches(self) -> list[dict[str, Any]]:
        return self.list_matches_from_competition_page(
            f"{COTEUR_WEB_BASE}/cotes/foot/monde/coupe-du-monde-2026"
        )

    def list_match_links_from_page(self, page_url: str) -> list[dict[str, Any]]:
        return self.list_matches_from_competition_page(page_url)

    def list_football_matches_from_homepage(self) -> list[dict[str, Any]]:
        response = self.session.get(f"{COTEUR_WEB_BASE}/", timeout=30)
        if response.status_code != 200:
            return []
        matches: dict[int, dict[str, Any]] = {}
        for slug, renc_id in re.findall(r'href="/cote/([^"]+)-(\d+)"', response.text):
            matches.setdefault(
                int(renc_id),
                {
                    "renc_id": int(renc_id),
                    "slug": slug,
                    "home_slug": slug.rsplit("-", 1)[0].replace("-", " "),
                    "away_slug": slug.rsplit("-", 1)[-1].replace("-", " "),
                    "url": f"{COTEUR_WEB_BASE}/cote/{slug}-{renc_id}",
                },
            )
        return list(matches.values())

    def list_football_competition_pages_from_match(self, match_url: str) -> list[str]:
        response = self.session.get(match_url, timeout=30)
        if response.status_code != 200:
            return []
        pages = {
            f"{COTEUR_WEB_BASE}{link}"
            for link in re.findall(r'href="(/cotes/foot[^"]+)"', response.text)
        }
        return sorted(pages)

    def list_football_competition_pages(self, seed_urls: list[str] | None = None) -> list[str]:
        seeds = list(seed_urls or [])
        discovered_from_matches: list[str] = []
        if not seeds:
            homepage = self.session.get(f"{COTEUR_WEB_BASE}/", timeout=30)
            if homepage.status_code == 200:
                for link in re.findall(r'href="(/cotes/foot[^"]+)"', homepage.text):
                    seeds.append(f"{COTEUR_WEB_BASE}{link}")
            for match in self.list_football_matches_from_homepage():
                try:
                    data = self.get_full_odds(match["renc_id"])
                except RuntimeError:
                    continue
                sport_name = ((data.get("info") or {}).get("sport") or {}).get("sportNom", "")
                if sport_name.lower() != "football":
                    continue
                discovered_from_matches.extend(self.list_football_competition_pages_from_match(match["url"]))
        seeds.extend(discovered_from_matches)
        seeds.extend(DEFAULT_FOOTBALL_COMPETITION_SEEDS)

        pages: set[str] = set()
        queue = list(dict.fromkeys(seeds))
        seen: set[str] = set()
        while queue:
            url = queue.pop(0)
            if url in seen:
                continue
            seen.add(url)
            response = self.session.get(url, timeout=30)
            if response.status_code != 200:
                continue
            if "/cotes/foot" in url:
                pages.add(url)
            for link in re.findall(r'href="(/cotes/foot[^"]+)"', response.text):
                full = f"{COTEUR_WEB_BASE}{link}"
                pages.add(full)
                if full not in seen:
                    queue.append(full)
        return sorted(pages)

    def list_football_matches(self, seed_urls: list[str] | None = None) -> list[dict[str, Any]]:
        matches: dict[int, dict[str, Any]] = {}
        for page_url in self.list_football_competition_pages(seed_urls):
            for match in self.list_matches_from_competition_page(page_url):
                matches.setdefault(match["renc_id"], match)
        for match in self.list_football_matches_from_homepage():
            matches.setdefault(match["renc_id"], match)

        football_matches = []
        for match in matches.values():
            try:
                data = self.get_full_odds(match["renc_id"])
            except RuntimeError:
                continue
            sport_name = ((data.get("info") or {}).get("sport") or {}).get("sportNom", "")
            if sport_name.lower() != "football":
                continue
            football_matches.append(match)
        return football_matches

    def list_tennis_matches_from_homepage(self) -> list[dict[str, Any]]:
        response = self.session.get(f"{COTEUR_WEB_BASE}/", timeout=30)
        if response.status_code != 200:
            return []
        matches: dict[int, dict[str, Any]] = {}
        for slug, renc_id in re.findall(r'href="/cote/([^"]+)-(\d+)"', response.text):
            matches.setdefault(
                int(renc_id),
                {
                    "renc_id": int(renc_id),
                    "slug": slug,
                    "home_slug": slug.rsplit("-", 1)[0].replace("-", " "),
                    "away_slug": slug.rsplit("-", 1)[-1].replace("-", " "),
                    "url": f"{COTEUR_WEB_BASE}/cote/{slug}-{renc_id}",
                },
            )
        return list(matches.values())

    def list_tennis_competition_pages_from_match(self, match_url: str) -> list[str]:
        response = self.session.get(match_url, timeout=30)
        if response.status_code != 200:
            return []
        pages = {
            f"{COTEUR_WEB_BASE}{link}"
            for link in re.findall(r'href="(/cotes/tennis[^"]+)"', response.text)
        }
        return sorted(pages)

    def list_tennis_competition_pages(self, seed_urls: list[str] | None = None) -> list[str]:
        seeds = list(seed_urls or [])
        discovered_from_matches: list[str] = []
        if not seeds:
            for match in self.list_tennis_matches_from_homepage():
                try:
                    data = self.get_full_odds(match["renc_id"])
                except RuntimeError:
                    continue
                sport_name = ((data.get("info") or {}).get("sport") or {}).get("sportNom", "")
                if sport_name.lower() != "tennis":
                    continue
                discovered_from_matches.extend(self.list_tennis_competition_pages_from_match(match["url"]))
        seeds.extend(discovered_from_matches)
        seeds.extend(DEFAULT_TENNIS_COMPETITION_SEEDS)
        pages: set[str] = set()
        queue = list(seeds)
        seen: set[str] = set()
        while queue:
            url = queue.pop(0)
            if url in seen:
                continue
            seen.add(url)
            response = self.session.get(url, timeout=30)
            if response.status_code != 200:
                continue
            if "/cotes/tennis" in url:
                pages.add(url)
            for link in re.findall(r'href="(/cotes/tennis[^"]+)"', response.text):
                full = f"{COTEUR_WEB_BASE}{link}"
                pages.add(full)
                if full not in seen:
                    queue.append(full)
        return sorted(pages)

    def list_tennis_matches(self, seed_urls: list[str] | None = None) -> list[dict[str, Any]]:
        matches: dict[int, dict[str, Any]] = {}
        candidate_urls = set(self.list_tennis_competition_pages(seed_urls))
        for page_url in candidate_urls:
            for match in self.list_matches_from_competition_page(page_url):
                matches.setdefault(match["renc_id"], match)
        for match in self.list_tennis_matches_from_homepage():
            matches.setdefault(match["renc_id"], match)
        tennis_matches = []
        for match in matches.values():
            try:
                data = self.get_full_odds(match["renc_id"])
            except RuntimeError:
                continue
            sport_name = ((data.get("info") or {}).get("sport") or {}).get("sportNom", "")
            if sport_name.lower() != "tennis":
                continue
            tennis_matches.append(match)
        return tennis_matches
