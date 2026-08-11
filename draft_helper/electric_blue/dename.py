"""Resolves Yahoo's UI-truncated team names (e.g. "By The Beard...") to
full names where known, using the one manager/team roster actually
captured (`data/electric_blue/research/managers_172092.csv`, the 2019-2020
era). Four team identities -- "By The Beard...", "Ron Mexico's...",
"Password Is ...", "Surrender Yo..." -- appear with the *identical*
truncated string in every single season 2019-2025, meaning the same four
managers kept the same team name the whole time; those get resolved with
full confidence across all seasons. Everything else only had a truncated
form ever observed (no full-roster pull exists for eras other than
172092), so those are left with the trailing "..." stripped rather than
guessed at.
"""
from __future__ import annotations

import os

import pandas as pd

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MANAGERS_PATH = os.path.join(BASE_DIR, "data", "electric_blue", "research", "managers_172092.csv")


def load_full_name_lookup(managers_path: str = MANAGERS_PATH) -> dict:
    """{truncated_prefix: full_team_name} for every team name in the known roster."""
    if not os.path.exists(managers_path):
        return {}
    managers = pd.read_csv(managers_path)
    lookup = {}
    for full_name in managers["team_name"].dropna():
        full_name = full_name.strip()
        # Truncated forms observed in the wild keep ~13-20 chars then "...".
        # Match by prefix rather than a fixed length since Yahoo's cutoff varies.
        lookup[full_name] = full_name
    return lookup


def resolve(team_name_raw: str, lookup: dict) -> str:
    team_name_raw = team_name_raw.strip()
    if not team_name_raw.endswith("..."):
        return team_name_raw  # never truncated, already the full name
    prefix = team_name_raw[:-3].strip()
    for full_name in lookup:
        if full_name.startswith(prefix):
            return full_name
    return prefix  # unresolved -- best-effort partial name, not guessed


def apply(df: pd.DataFrame, managers_path: str = MANAGERS_PATH) -> pd.DataFrame:
    lookup = load_full_name_lookup(managers_path)
    out = df.copy()
    out["team_name"] = out["team_name_raw"].apply(lambda t: resolve(t, lookup))
    out["team_name_resolved"] = out["team_name"] != out["team_name_raw"].str.rstrip(".")
    return out
