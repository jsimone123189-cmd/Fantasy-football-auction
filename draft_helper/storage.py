"""CSV cache for pulled Yahoo data, so re-running analysis doesn't re-hit the API."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

RAW_DIR = Path("data/raw")
KEEPERS_DIR = Path("data/keepers")

DRAFT_COLUMNS = [
    "season",
    "league_key",
    "pick",
    "round",
    "team_key",
    "team_name",
    "manager_name",
    "manager_guid",
    "player_key",
    "player_name",
    "position",
    "nfl_team",
    "cost",
    "is_keeper",
]


def draft_csv_path(season: str) -> Path:
    return RAW_DIR / f"{season}_draft.csv"


def teams_csv_path(season: str) -> Path:
    return RAW_DIR / f"{season}_teams.csv"


def keepers_csv_path(season: str) -> Path:
    return KEEPERS_DIR / f"{season}.csv"


def save_draft(season: str, rows: list[dict]) -> Path:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(rows)
    for col in DRAFT_COLUMNS:
        if col not in df.columns:
            df[col] = None
    df = df[DRAFT_COLUMNS]
    path = draft_csv_path(season)
    df.to_csv(path, index=False)
    return path


def save_teams(season: str, rows: list[dict]) -> Path:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(rows)
    path = teams_csv_path(season)
    df.to_csv(path, index=False)
    return path


def load_keeper_overrides(season: str) -> pd.DataFrame:
    """Optional manual overrides: data/keepers/{season}.csv with columns
    team_name,player_name,is_keeper (1/0). Yahoo's API does not reliably expose
    keeper status for auction drafts, so this fills the gap from what you can
    see on Yahoo's draft recap page (keepers are marked there).
    """
    path = keepers_csv_path(season)
    if not path.exists():
        return pd.DataFrame(columns=["team_name", "player_name", "is_keeper"])
    return pd.read_csv(path)


def available_seasons() -> list[str]:
    if not RAW_DIR.exists():
        return []
    seasons = sorted(
        p.name.split("_draft.csv")[0] for p in RAW_DIR.glob("*_draft.csv")
    )
    return seasons


def load_all_drafts() -> pd.DataFrame:
    frames = []
    for season in available_seasons():
        df = pd.read_csv(draft_csv_path(season), dtype={"season": str})
        frames.append(df)
    if not frames:
        return pd.DataFrame(columns=DRAFT_COLUMNS)
    return pd.concat(frames, ignore_index=True)


def load_season(season: str) -> pd.DataFrame:
    path = draft_csv_path(season)
    if not path.exists():
        raise FileNotFoundError(f"No cached draft data for {season}: {path}")
    return pd.read_csv(path, dtype={"season": str})
