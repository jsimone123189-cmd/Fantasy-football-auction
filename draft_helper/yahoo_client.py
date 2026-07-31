"""Thin wrapper around the Yahoo Fantasy Sports REST API (NFL, auction leagues).

Only reads the endpoints this project needs: league discovery across seasons,
teams/managers, draft results, and player metadata. See parsing.py for notes
on Yahoo's JSON shape.

NOTE: this was written against Yahoo's documented/publicly-known response
shape, not verified against a live account (that requires a real Yahoo login,
which only you can do). If a field comes back missing/None after your first
real `fetch-history` run, use `debug-endpoint` (see cli.py) to dump the raw
JSON for the offending endpoint and adjust the extract_* function here.
"""
from __future__ import annotations

import logging
import time
from typing import Iterable, Optional

import requests

from .auth import YahooOAuth
from .parsing import iter_collection, merge_fragments

BASE_URL = "https://fantasysports.yahooapis.com/fantasy/v2"

logger = logging.getLogger(__name__)


class YahooApiError(RuntimeError):
    pass


class YahooFantasyClient:
    def __init__(self, oauth: YahooOAuth):
        self.oauth = oauth
        self.session = requests.Session()

    def _get(self, path: str, params: Optional[dict] = None, _retry: bool = True) -> dict:
        url = f"{BASE_URL}{path}"
        params = dict(params or {})
        params["format"] = "json"
        token = self.oauth.get_valid_access_token()
        resp = self.session.get(
            url,
            params=params,
            headers={"Authorization": f"Bearer {token}"},
            timeout=30,
        )
        if resp.status_code == 401 and _retry:
            self.oauth.refresh()
            return self._get(path, params, _retry=False)
        if resp.status_code == 999:
            raise YahooApiError("Rate limited by Yahoo (999). Slow down and retry later.")
        if resp.status_code != 200:
            raise YahooApiError(f"GET {url} failed ({resp.status_code}): {resp.text[:500]}")
        try:
            return resp.json()
        except ValueError as e:
            raise YahooApiError(f"Non-JSON response from {url}: {resp.text[:500]}") from e

    def raw_get(self, path: str, params: Optional[dict] = None) -> dict:
        """Fetch raw JSON for an arbitrary endpoint path — used by the
        `debug-endpoint` CLI command when troubleshooting response shapes."""
        return self._get(path, params)

    # -- league discovery -------------------------------------------------

    def get_user_leagues(self, game_codes: str = "nfl") -> list[dict]:
        """All of the logged-in user's leagues across every NFL season.

        Returns dicts with league_key, league_id, name, season, draft_status.
        """
        data = self._get(f"/users;use_login=1/games;game_codes={game_codes}/leagues")
        leagues: list[dict] = []
        try:
            users = data["fantasy_content"]["users"]
        except KeyError:
            return leagues
        for user_item in iter_collection(users):
            user = merge_fragments(user_item.get("user"))
            games = user.get("games")
            for game_item in iter_collection(games):
                game = merge_fragments(game_item.get("game"))
                season = game.get("season")
                for league_item in iter_collection(game.get("leagues")):
                    league = merge_fragments(league_item.get("league"))
                    if league:
                        league.setdefault("season", season)
                        leagues.append(league)
        return leagues

    def get_league_settings(self, league_key: str) -> dict:
        data = self._get(f"/league/{league_key}/settings")
        league = merge_fragments(data.get("fantasy_content", {}).get("league"))
        settings = merge_fragments(league.get("settings"))
        return settings

    # -- teams / managers ---------------------------------------------------

    def get_league_teams(self, league_key: str) -> list[dict]:
        data = self._get(f"/league/{league_key}/teams")
        league = merge_fragments(data.get("fantasy_content", {}).get("league"))
        teams_out: list[dict] = []
        for team_item in iter_collection(league.get("teams")):
            team = merge_fragments(team_item.get("team"))
            manager_name, manager_guid = self._extract_manager(team.get("managers"))
            teams_out.append(
                {
                    "team_key": team.get("team_key"),
                    "team_id": team.get("team_id"),
                    "team_name": team.get("name"),
                    "manager_name": manager_name,
                    "manager_guid": manager_guid,
                }
            )
        return teams_out

    @staticmethod
    def _extract_manager(managers_field) -> tuple[Optional[str], Optional[str]]:
        for item in iter_collection(managers_field):
            manager = item.get("manager") if isinstance(item, dict) else None
            if manager is None:
                continue
            if isinstance(manager, list):
                manager = merge_fragments(manager)
            if isinstance(manager, dict):
                return manager.get("nickname"), manager.get("guid")
        return None, None

    # -- draft results --------------------------------------------------

    def get_draft_results(self, league_key: str) -> list[dict]:
        """Raw picks: pick, round, team_key, player_key, cost (auction $), is_keeper if present."""
        data = self._get(f"/league/{league_key}/draftresults")
        league = merge_fragments(data.get("fantasy_content", {}).get("league"))
        picks: list[dict] = []
        for item in iter_collection(league.get("draft_results")):
            pick = merge_fragments(item.get("draft_result"))
            if pick:
                picks.append(pick)
        return picks

    # -- players ------------------------------------------------------------

    def get_players_by_keys(self, league_key: str, player_keys: Iterable[str]) -> dict[str, dict]:
        """Batch player metadata lookup: player_key -> {name, position, nfl_team}."""
        keys = list(dict.fromkeys(k for k in player_keys if k))
        out: dict[str, dict] = {}
        chunk_size = 25
        for i in range(0, len(keys), chunk_size):
            chunk = keys[i : i + chunk_size]
            key_str = ",".join(chunk)
            data = self._get(f"/league/{league_key}/players;player_keys={key_str}")
            league = merge_fragments(data.get("fantasy_content", {}).get("league"))
            for item in iter_collection(league.get("players")):
                player = merge_fragments(item.get("player"))
                pkey = player.get("player_key")
                if not pkey:
                    continue
                name = player.get("name") or {}
                if isinstance(name, list):
                    name = merge_fragments(name)
                out[pkey] = {
                    "player_name": name.get("full"),
                    "position": player.get("display_position") or player.get("primary_position"),
                    "nfl_team": player.get("editorial_team_abbr"),
                }
            if i + chunk_size < len(keys):
                time.sleep(0.2)  # be polite to Yahoo's rate limiter
        return out
