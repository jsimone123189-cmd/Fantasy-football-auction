"""Snake-draft value ranking for Rivals FCL -- there's no auction $, so
instead of `analysis/inflation.py`'s historical price curve, players are
ranked by Value Over Replacement (VOR): projected points above the last
player at that position who'd still be a normal starter across the league.

Replacement rank per position = (starters/team x teams) + that position's
share of the league's FLEX slots (RWT = RB/WR/TE).

The flex-share split below is *empirically measured*, not guessed: earlier
this project assumed 30% RB / 60% WR / 10% TE on the reasoning that 3
dedicated WR slots vs. 1 dedicated RB slot means WR dominates the flex too.
That reasoning is backwards for this format. Running the neutral
best-value-available 16-team draft sim (mock_draft.py) 300 times with
small tie-breaking jitter and checking who actually wins each team's flex
slot converged tightly on RB 50% / WR 31% / TE 19% (4,800 flex picks
sampled, stable to within rounding across trials) -- because with only 1
dedicated RB slot, a team's RB2 is very often still better than its WR4
in this scoring format (full PPR softens the receiving-back floor, and
RB value falls off a cliff past the top tier), so RB ends up winning the
flex more often than the slot count alone would suggest. See
tests/test_value_flex_share.py for the reproducible measurement.

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
FLEX_SHARE = {"RB": 0.50, "WR": 0.3125, "TE": 0.1875}


def replacement_ranks(num_teams: int = NUM_TEAMS) -> dict:
    ranks = {}
    for pos, n in STARTERS.items():
        extra = FLEX_SLOTS_PER_TEAM * num_teams * FLEX_SHARE.get(pos, 0.0)
        ranks[pos] = max(1, round(num_teams * n + extra))
    return ranks


def position_replacement_points(df: pd.DataFrame, value_col: str, num_teams: int = NUM_TEAMS) -> dict:
    """The `value_col` score of the last player at each position who'd
    still start somewhere across `num_teams` teams (accounting for FLEX
    demand) -- the replacement-level baseline VOR is measured against.
    """
    ranks = replacement_ranks(num_teams)
    replacement_points = {}
    for pos, rep_rank in ranks.items():
        pos_df = df[df["position"] == pos].sort_values(value_col, ascending=False)
        if pos_df.empty:
            replacement_points[pos] = 0.0
            continue
        idx = min(rep_rank, len(pos_df)) - 1
        replacement_points[pos] = float(pos_df.iloc[idx][value_col])
    return replacement_points


def position_vor(df: pd.DataFrame, value_col: str, num_teams: int = NUM_TEAMS) -> pd.Series:
    """Row-aligned VOR (`value_col` minus that row's position replacement
    level) without sorting or ranking -- the building block `compute_vor`
    uses, and reusable on its own when a caller needs to blend VOR from
    more than one `value_col` (e.g. combining VOR computed separately per
    phase of a split season) before doing a single final rank/sort.
    Critically, computing VOR *before* blending -- rather than blending
    raw points and taking VOR once at the end -- keeps a multi-phase blend
    from being skewed by the sheer scale of one position's raw point
    totals (e.g. QB volume stats in a format that scores 0.04 pt/pass
    yard): VOR is already scale-normalized per position, so it blends
    fairly across positions in a way raw points don't.
    """
    replacement_points = position_replacement_points(df, value_col, num_teams)
    replacement = df["position"].map(replacement_points).fillna(0.0)
    return (df[value_col] - replacement).round(1)


def compute_vor(df: pd.DataFrame, num_teams: int = NUM_TEAMS, value_col: str = "projected_points") -> pd.DataFrame:
    """df needs columns: player_name, position, and `value_col` (median
    points by default). Adds: pos_rank, replacement_points, vor,
    overall_rank, vor_round -- all computed off `value_col`, so passing a
    weighted value (e.g. one that overweights certain weeks) shifts VOR
    and draft order without touching the real `projected_points` column
    used for display.
    """
    out = df.copy()
    out["pos_rank"] = out.groupby("position")[value_col].rank(
        ascending=False, method="first"
    ).astype(int)

    replacement_points = position_replacement_points(out, value_col, num_teams)
    out["replacement_points"] = out["position"].map(replacement_points).fillna(0.0)
    out["vor"] = position_vor(out, value_col, num_teams)

    out = out.sort_values("vor", ascending=False).reset_index(drop=True)
    out["overall_rank"] = out.index + 1
    out["vor_round"] = out["overall_rank"].apply(lambda r: math.ceil(r / num_teams))
    return out


def rank_from_vor(df: pd.DataFrame, num_teams: int = NUM_TEAMS) -> pd.DataFrame:
    """Like the tail of `compute_vor`, but for when `vor` has already been
    computed elsewhere (e.g. a blend of per-phase VOR) instead of being
    derived fresh from a single `value_col`. Sorts by the existing `vor`
    column and (re)assigns overall_rank/vor_round from that order.
    """
    out = df.sort_values("vor", ascending=False).reset_index(drop=True)
    out["overall_rank"] = out.index + 1
    out["vor_round"] = out["overall_rank"].apply(lambda r: math.ceil(r / num_teams))
    return out
