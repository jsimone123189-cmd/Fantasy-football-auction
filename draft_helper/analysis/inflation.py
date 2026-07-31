"""Historical price curve: what share of the total auction pool your league
has actually paid for the Nth-most-expensive player at each position, averaged
across your drafted seasons. This is the "expected value" baseline the cheat
sheet and live assistant price players against, adjusted for real-time
inflation (see baseline_value / inflation_rate below).
"""
from __future__ import annotations

import pandas as pd

MIN_DOLLAR = 1.0


def build_position_rank_curve(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["cost"] = pd.to_numeric(df["cost"], errors="coerce").fillna(0)
    season_total = df.groupby("season")["cost"].transform("sum")
    df["cost_share"] = df["cost"] / season_total.where(season_total != 0, other=pd.NA)
    df["pos_rank"] = df.groupby(["season", "position"])["cost"].rank(method="first", ascending=False)

    curve = (
        df.dropna(subset=["cost_share"])
        .groupby(["position", "pos_rank"])["cost_share"]
        .agg(avg_cost_share="mean", seasons_seen="count")
        .reset_index()
        .sort_values(["position", "pos_rank"])
        .reset_index(drop=True)
    )
    return curve


def baseline_value(curve: pd.DataFrame, position: str, rank: int, total_budget: float) -> float:
    """Expected $ price for the Nth-ranked player at `position` this year,
    scaled to this year's total auction pool (num_teams * budget_per_team).
    """
    exact = curve[(curve["position"] == position) & (curve["pos_rank"] == rank)]
    if not exact.empty:
        share = exact["avg_cost_share"].iat[0]
    else:
        pos_rows = curve[curve["position"] == position]
        if pos_rows.empty:
            return MIN_DOLLAR
        nearest_idx = (pos_rows["pos_rank"] - rank).abs().idxmin()
        share = pos_rows.loc[nearest_idx, "avg_cost_share"]
    return max(MIN_DOLLAR, round(float(share) * total_budget, 1))


def inflation_rate(total_budget: float, dollars_spent: float, baseline_value_drafted: float, baseline_value_total: float) -> float:
    """Standard auction-inflation formula: ratio of $ actually left in the pool
    to the baseline value still on the board. >1 means the room is paying
    above historical norms (inflated); <1 means bargains are out there.
    """
    dollars_remaining = total_budget - dollars_spent
    baseline_remaining = baseline_value_total - baseline_value_drafted
    if baseline_remaining <= 0:
        return 1.0
    return dollars_remaining / baseline_remaining
