"""Pull a league's full auction draft history from Yahoo and cache it as CSV."""
from __future__ import annotations

import logging

from . import storage
from .yahoo_client import YahooFantasyClient

logger = logging.getLogger(__name__)


def discover_league_keys(client: YahooFantasyClient, league_id: str) -> dict[str, str]:
    """season -> league_key for every year the given league_id appears in the
    logged-in user's league history. Yahoo keeps league_id stable across a
    renewed league's seasons; game_key (and therefore league_key) changes
    every year.
    """
    leagues = client.get_user_leagues()
    out: dict[str, str] = {}
    for league in leagues:
        lid = str(league.get("league_id") or "")
        lkey = league.get("league_key") or ""
        if lid == str(league_id) or lkey.endswith(f".l.{league_id}"):
            season = str(league.get("season") or "")
            if season:
                out[season] = lkey
    return out


def fetch_and_cache_season(client: YahooFantasyClient, season: str, league_key: str) -> dict:
    """Fetch teams + draft results + player metadata for one season and write CSVs.

    Returns a small summary dict for reporting to the user.
    """
    settings = client.get_league_settings(league_key)
    draft_type = settings.get("draft_type")
    if draft_type and draft_type != "auction":
        logger.warning(
            "%s: draft_type=%r (not 'auction') — skipping, this league wasn't an "
            "auction that year.",
            season,
            draft_type,
        )
        return {"season": season, "skipped": True, "reason": f"draft_type={draft_type}"}

    teams = client.get_league_teams(league_key)
    teams_by_key = {t["team_key"]: t for t in teams}
    storage.save_teams(season, teams)

    picks = client.get_draft_results(league_key)
    player_keys = [p.get("player_key") for p in picks]
    players = client.get_players_by_keys(league_key, player_keys)

    keeper_overrides = storage.load_keeper_overrides(season)

    rows = []
    for pick in picks:
        team = teams_by_key.get(pick.get("team_key"), {})
        player = players.get(pick.get("player_key"), {})
        row = {
            "season": season,
            "league_key": league_key,
            "pick": pick.get("pick"),
            "round": pick.get("round"),
            "team_key": pick.get("team_key"),
            "team_name": team.get("team_name"),
            "manager_name": team.get("manager_name"),
            "manager_guid": team.get("manager_guid"),
            "player_key": pick.get("player_key"),
            "player_name": player.get("player_name"),
            "position": player.get("position"),
            "nfl_team": player.get("nfl_team"),
            "cost": pick.get("cost"),
            "is_keeper": pick.get("is_keeper", False),
        }
        if not keeper_overrides.empty:
            match = keeper_overrides[
                (keeper_overrides["team_name"] == row["team_name"])
                & (keeper_overrides["player_name"] == row["player_name"])
            ]
            if not match.empty:
                row["is_keeper"] = bool(match.iloc[0]["is_keeper"])
        rows.append(row)

    path = storage.save_draft(season, rows)
    return {"season": season, "league_key": league_key, "picks": len(rows), "path": str(path)}


def fetch_history(
    client: YahooFantasyClient,
    league_id: str | None = None,
    league_keys: dict[str, str] | None = None,
) -> list[dict]:
    """Fetch every auction season for the league, either auto-discovered by
    league_id or from an explicit {season: league_key} map (see `leagues`
    CLI command to find keys manually if auto-discovery misses a year).
    """
    if league_keys is None:
        if not league_id:
            raise ValueError("Provide league_id or an explicit league_keys map.")
        league_keys = discover_league_keys(client, league_id)
    if not league_keys:
        raise RuntimeError(
            "No leagues found for that league_id. Run `draft-helper leagues` to "
            "see everything Yahoo has on file for your account and pass "
            "--league-keys explicitly if the id changed across seasons."
        )

    results = []
    for season, league_key in sorted(league_keys.items()):
        logger.info("Fetching %s (%s)...", season, league_key)
        results.append(fetch_and_cache_season(client, season, league_key))
    return results
