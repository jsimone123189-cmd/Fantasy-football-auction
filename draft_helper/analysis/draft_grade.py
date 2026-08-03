"""Post-draft grading: how each team's actual draft stacks up on the two
things that matter -- roster strength (projected points from the starting
lineup they can actually field) and value (did they pay above or below
this year's fair price for what they got).

Deliberately does NOT penalize a team for skipping a backup DEF/backup QB/
2nd TE the way some default auto-grade tools do. Those tools often simulate
the season using only the literal drafted roster, so any position you
didn't double up on scores as a hard zero on bye weeks -- as if you'd
never make a waiver claim all year. In practice almost nobody rosters a
2nd DEF or backup QB/TE; those are streamed. Grading off of the real
players a team actually drafted (not a hypothetical empty bench slot)
avoids manufacturing a penalty for a perfectly normal roster-construction
choice.
"""
from __future__ import annotations

import pandas as pd

from .roster_needs import DEFAULT_SLOTS, FLEX_ELIGIBLE, compute_needs, format_needs

GRADE_BANDS = [
    (0.93, "A+"), (0.87, "A"), (0.80, "A-"),
    (0.73, "B+"), (0.67, "B"), (0.60, "B-"),
    (0.53, "C+"), (0.47, "C"), (0.40, "C-"),
    (0.33, "D+"), (0.27, "D"), (0.20, "D-"),
]


def _letter_grade(percentile: float) -> str:
    for cutoff, letter in GRADE_BANDS:
        if percentile >= cutoff:
            return letter
    return "F"


def _optimal_lineup_points(team_df: pd.DataFrame, slots: dict) -> tuple[float, set]:
    """Greedily assigns this team's drafted players to starting slots by
    projected points (own-position slots first, then FLEX), returning the
    total starting-lineup points and the index set of players who started.
    """
    slots = dict(slots)
    flex_n = slots.pop("FLEX", 0)
    used: set = set()
    total = 0.0
    for pos, n in slots.items():
        candidates = team_df[
            (team_df["position"] == pos) & (~team_df.index.isin(used))
        ].sort_values("projected_points", ascending=False)
        picks = candidates.head(n)
        used.update(picks.index)
        total += picks["projected_points"].sum()
    flex_candidates = team_df[
        team_df["position"].isin(FLEX_ELIGIBLE) & (~team_df.index.isin(used))
    ].sort_values("projected_points", ascending=False)
    flex_picks = flex_candidates.head(flex_n)
    used.update(flex_picks.index)
    total += flex_picks["projected_points"].sum()
    return total, used


def grade_draft(
    log: pd.DataFrame,
    projections: pd.DataFrame,
    starting_slots: dict | None = None,
) -> pd.DataFrame:
    """log: a completed draft log with player_name, position, team_name, cost
    (the format `draft-helper live` saves to draft_log.csv).
    projections: this year's projections (player_name, position,
    projected_points, baseline_value or the columns cheat-sheet produces).

    Returns one row per team, sorted best grade first, with columns:
    team_name, spent, starting_points, roster_points, value_surplus, grade,
    best_value (name, surplus), worst_value (name, surplus), needs (text).
    """
    slots = starting_slots or DEFAULT_SLOTS
    proj_cols = projections[["player_name", "projected_points", "baseline_value"]] if (
        "baseline_value" in projections.columns
    ) else projections[["player_name", "projected_points"]]

    merged = log.merge(proj_cols, on="player_name", how="left", suffixes=("", "_proj"))
    merged["projected_points"] = merged["projected_points"].fillna(0.0)
    if "baseline_value" not in merged.columns:
        merged["baseline_value"] = merged.get("baseline_value_proj", 0.0)
    merged["baseline_value"] = merged["baseline_value"].fillna(0.0)
    merged["value_delta"] = merged["baseline_value"] - merged["cost"]

    rows = []
    for team_name, team_df in merged.groupby("team_name"):
        team_df = team_df.reset_index(drop=True)
        starting_points, started_idx = _optimal_lineup_points(team_df, slots)
        roster_points = team_df["projected_points"].sum()
        spent = team_df["cost"].sum()
        value_surplus = team_df["value_delta"].sum()

        best_value = team_df.loc[team_df["value_delta"].idxmax()]
        worst_value = team_df.loc[team_df["value_delta"].idxmin()]

        needs = compute_needs(team_df["position"].tolist(), slots)

        rows.append({
            "team_name": team_name,
            "spent": spent,
            "starting_points": starting_points,
            "roster_points": roster_points,
            "value_surplus": value_surplus,
            "best_value_name": best_value["player_name"],
            "best_value_delta": best_value["value_delta"],
            "worst_value_name": worst_value["player_name"],
            "worst_value_delta": worst_value["value_delta"],
            "needs": format_needs(needs),
        })

    grades = pd.DataFrame(rows)
    if grades.empty:
        return grades

    def _z(series: pd.Series) -> pd.Series:
        std = series.std(ddof=0)
        if not std:
            return pd.Series(0.0, index=series.index)
        return (series - series.mean()) / std

    composite = 0.5 * _z(grades["starting_points"]) + 0.5 * _z(grades["value_surplus"])
    grades["percentile"] = composite.rank(pct=True)
    grades["grade"] = grades["percentile"].apply(_letter_grade)
    grades = grades.sort_values("percentile", ascending=False).reset_index(drop=True)
    return grades
