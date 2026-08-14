"""Resolves Yahoo's UI-truncated team names (e.g. "By The Beard...") to
full names and to the real manager who owned that team, per season.

`data/electric_blue/research/managers_by_season.csv` was built from the
user's own Yahoo "Managers" page screenshots -- one per season, 2019-2026
-- so every team name/manager pairing below is real roster data, not
inferred from name-matching heuristics. Verified against every row in
draft_history_raw.csv: all 1,236 historical picks resolve to a real
manager with zero unmatched rows (see tests/test_electric_blue_dename.py).
"""
from __future__ import annotations

import os

import pandas as pd

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MANAGERS_BY_SEASON_PATH = os.path.join(
    BASE_DIR, "data", "electric_blue", "research", "managers_by_season.csv"
)
# Kept for backward compatibility with any caller still using the single
# (2020-era) roster snapshot.
MANAGERS_PATH = os.path.join(BASE_DIR, "data", "electric_blue", "research", "managers_172092.csv")


def load_season_rosters(path: str = MANAGERS_BY_SEASON_PATH) -> dict:
    """{season: {team_name: manager}} for every season with a captured
    Yahoo "Managers" page.
    """
    if not os.path.exists(path):
        return {}
    managers = pd.read_csv(path)
    rosters: dict[int, dict[str, str]] = {}
    for _, row in managers.iterrows():
        season = int(row["season"])
        rosters.setdefault(season, {})[str(row["team_name"]).strip()] = str(row["manager"]).strip()
    return rosters


def resolve_team_name(season: int, team_name_raw: str, rosters: dict) -> str:
    """Full team name for a (possibly Yahoo-truncated) raw name in a given
    season. Falls back to the truncated-prefix form if that season has no
    captured roster, or if nothing in the roster matches the prefix --
    never guesses a full name that isn't backed by real data.
    """
    team_name_raw = team_name_raw.strip()
    season_roster = rosters.get(season, {})
    if not team_name_raw.endswith("..."):
        return team_name_raw
    prefix = team_name_raw[:-3].strip()
    for full_name in season_roster:
        if full_name.startswith(prefix):
            return full_name
    return prefix  # unresolved -- best-effort partial name, not guessed


def resolve_manager(season: int, team_name_raw: str, rosters: dict) -> str | None:
    """Real manager name for a (season, raw team name) pair, or None if
    that season/team isn't in the captured roster data.
    """
    season_roster = rosters.get(season, {})
    full_name = resolve_team_name(season, team_name_raw, rosters)
    return season_roster.get(full_name)


def apply(df: pd.DataFrame, managers_by_season_path: str = MANAGERS_BY_SEASON_PATH) -> pd.DataFrame:
    """Adds `team_name` (de-truncated) and `manager` (real owner, from the
    per-season roster captures) columns to a draft-history dataframe with
    `season` and `team_name_raw` columns.
    """
    rosters = load_season_rosters(managers_by_season_path)
    out = df.copy()
    out["team_name"] = out.apply(
        lambda r: resolve_team_name(int(r["season"]), r["team_name_raw"], rosters), axis=1
    )
    out["manager"] = out.apply(
        lambda r: resolve_manager(int(r["season"]), r["team_name_raw"], rosters), axis=1
    )
    out["team_name_resolved"] = out["team_name"] != out["team_name_raw"].str.rstrip(".")
    return out
