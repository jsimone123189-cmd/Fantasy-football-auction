"""Snake-draft VOR ranking for Electric Blue -- same approach as Rivals FCL
(no auction $ here either), but a different roster shape: QB, RB, RB, WR,
WR, TE, W/R/T flex, K, DEF (12 teams). The flex is a true 3-way RB/WR/TE
split rather than Rivals' RB/WR-leaning split, since this is half-PPR (not
full) and has 2 dedicated RB slots already, so there's less structural bias
toward any one flex-eligible position.
"""
from __future__ import annotations

import math

import pandas as pd

NUM_TEAMS = 12
STARTERS = {"QB": 1, "RB": 2, "WR": 2, "TE": 1, "K": 1, "DEF": 1}
FLEX_SLOTS_PER_TEAM = 1
FLEX_SHARE = {"RB": 0.40, "WR": 0.45, "TE": 0.15}


def replacement_ranks(num_teams: int = NUM_TEAMS) -> dict:
    ranks = {}
    for pos, n in STARTERS.items():
        extra = FLEX_SLOTS_PER_TEAM * num_teams * FLEX_SHARE.get(pos, 0.0)
        ranks[pos] = max(1, round(num_teams * n + extra))
    return ranks


def compute_vor(df: pd.DataFrame, num_teams: int = NUM_TEAMS) -> pd.DataFrame:
    out = df.copy()
    out["pos_rank"] = out.groupby("position")["projected_points"].rank(ascending=False, method="first").astype(int)

    ranks = replacement_ranks(num_teams)
    replacement_points = {}
    for pos, rep_rank in ranks.items():
        pos_df = out[out["position"] == pos].sort_values("projected_points", ascending=False)
        if pos_df.empty:
            replacement_points[pos] = 0.0
            continue
        idx = min(rep_rank, len(pos_df)) - 1
        replacement_points[pos] = float(pos_df.iloc[idx]["projected_points"])

    out["replacement_points"] = out["position"].map(replacement_points).fillna(0.0)
    out["vor"] = (out["projected_points"] - out["replacement_points"]).round(1)

    out = out.sort_values("vor", ascending=False).reset_index(drop=True)
    out["overall_rank"] = out.index + 1
    out["vor_round"] = out["overall_rank"].apply(lambda r: math.ceil(r / num_teams))
    return out
