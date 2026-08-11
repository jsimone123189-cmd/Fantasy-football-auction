"""Small, reusable summary stats pulled from `data/rivals/2026.csv` for the
Rivals League strategy report -- keeps the report's numeric callouts
(replacement-level gaps, bye-week collisions among startable players) as
real computed values instead of hand-typed arithmetic that can drift out of
sync with the actual data.
"""
from __future__ import annotations

import pandas as pd


def position_summary(df: pd.DataFrame) -> pd.DataFrame:
    """Per position: how many players clear a plausible "startable" VOR bar
    (>0, i.e. better than replacement level) and where the top of that
    position sits relative to replacement.
    """
    rows = []
    for pos, g in df.groupby("position"):
        startable = g[g["vor"] > 0]
        rows.append({
            "position": pos,
            "n_startable": len(startable),
            "top_points": g["projected_points"].max(),
            "top_vor": g["vor"].max(),
            "replacement_points": g["replacement_points"].iloc[0] if "replacement_points" in g else None,
        })
    return pd.DataFrame(rows).sort_values("top_vor", ascending=False).reset_index(drop=True)


def bye_week_collisions(df: pd.DataFrame, vor_round_cutoff: int = 10) -> pd.DataFrame:
    """Among draft-relevant players (top `vor_round_cutoff` rounds by VOR),
    how many share each bye week -- flags weeks where a manager is likely
    to be caught needing 2+ replacements at once. Restricted to weeks 8-12
    (the Rivals knockout-relevant stretch).
    """
    relevant = df[(df["vor_round"] <= vor_round_cutoff) & df["bye_week"].notna()]
    relevant = relevant[relevant["bye_week"].isin([8, 9, 10, 11, 12])]
    rows = []
    for week, g in relevant.groupby("bye_week"):
        rows.append({
            "bye_week": int(week),
            "n_players": len(g),
            "players": ", ".join(g.sort_values("overall_rank")["player_name"].head(8)),
        })
    return pd.DataFrame(rows).sort_values("bye_week").reset_index(drop=True)


def replacement_gap(df: pd.DataFrame, pos_a: str, pos_b: str, rank: int = 1) -> float:
    """Points gap between the Nth-best player at pos_a vs pos_b -- used to
    back up "an elite LB is worth more than a mid RB1" style claims with a
    real number instead of an assertion.
    """
    a = df[df["position"] == pos_a].sort_values("projected_points", ascending=False)
    b = df[df["position"] == pos_b].sort_values("projected_points", ascending=False)
    if len(a) < rank or len(b) < rank:
        return float("nan")
    return round(float(a.iloc[rank - 1]["projected_points"] - b.iloc[rank - 1]["projected_points"]), 1)
