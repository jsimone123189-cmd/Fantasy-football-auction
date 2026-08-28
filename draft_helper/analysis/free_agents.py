"""Who's actually still available: this year's full player pool minus
everyone already on a roster, matched by normalized name so a suffix
mismatch (Jr./Sr./II/III, periods, apostrophes) between the draft log and
the projections file doesn't produce a false "free agent."
"""
from __future__ import annotations

import re

import pandas as pd

_SUFFIX_RE = re.compile(r"\b(jr|sr|ii|iii|iv)\b")
_PUNCT_RE = re.compile(r"[.\']")
_SPACE_RE = re.compile(r"\s+")


def normalize_name(name: str) -> str:
    name = _PUNCT_RE.sub("", str(name).lower())
    name = _SUFFIX_RE.sub("", name)
    return _SPACE_RE.sub(" ", name).strip()


def compute_free_agents(draft_df: pd.DataFrame, projections_df: pd.DataFrame) -> pd.DataFrame:
    """draft_df: a draft/roster log with a player_name column (e.g. data/raw/{season}_draft.csv,
    or that file plus any logged season moves).
    projections_df: this year's full player pool (e.g. cheat_sheet_2026.csv) with player_name,
    position, projected_points, and a $ column (target_price or baseline_value).

    Returns projections_df filtered to undrafted players, sorted by value descending.
    """
    drafted_norm = set(draft_df["player_name"].apply(normalize_name))
    out = projections_df.copy()
    out["_norm"] = out["player_name"].apply(normalize_name)
    out = out[~out["_norm"].isin(drafted_norm)].drop(columns="_norm")
    value_col = "target_price" if "target_price" in out.columns else "baseline_value"
    return out.sort_values(value_col, ascending=False).reset_index(drop=True)
