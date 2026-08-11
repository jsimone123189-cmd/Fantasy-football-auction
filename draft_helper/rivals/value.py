"""Snake-draft value ranking for Rivals FCL -- there's no auction $, so
instead of `analysis/inflation.py`'s historical price curve, players are
ranked by Value Over Replacement (VOR): projected points above the last
player at that position who'd still be a normal starter across the league.

Replacement rank per position = (starters/team x teams) + that position's
share of the league's FLEX slots (RWT = RB/WR/TE). The flex-share split
(30% RB / 60% WR / 10% TE) reflects that in a full-PPR league with only one
dedicated RB slot but three dedicated WR slots, teams overwhelmingly start
extra WRs and RBs in the flex, not TEs.

`vor_round` translates VOR rank into "this is a round N pick" for a 16-team
snake draft, which is the practical unit managers actually think in --
more useful on a cheat sheet than an abstract tier number.
"""
from __future__ import annotations

import math

import pandas as pd

NUM_TEAMS = 16
STARTERS = {"QB": 1, "RB": 1, "WR": 3, "TE": 1, "DL": 1, "LB": 1, "DB": 1, "K": 1}
FLEX_SLOTS_PER_TEAM = 1
FLEX_SHARE = {"RB": 0.30, "WR": 0.60, "TE": 0.10}


def replacement_ranks(num_teams: int = NUM_TEAMS) -> dict:
    ranks = {}
    for pos, n in STARTERS.items():
        extra = FLEX_SLOTS_PER_TEAM * num_teams * FLEX_SHARE.get(pos, 0.0)
        ranks[pos] = max(1, round(num_teams * n + extra))
    return ranks


def compute_vor(df: pd.DataFrame, num_teams: int = NUM_TEAMS) -> pd.DataFrame:
    """df needs columns: player_name, position, projected_points (median).
    Adds: pos_rank, replacement_points, vor, overall_rank, vor_round.
    """
    out = df.copy()
    out["pos_rank"] = out.groupby("position")["projected_points"].rank(
        ascending=False, method="first"
    ).astype(int)

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
