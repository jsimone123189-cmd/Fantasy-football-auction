"""Post-draft grading for Electric Blue's real 2026 snake draft.

Same two-factor idea as Top Teamz's auction grader (draft_helper.
analysis.draft_grade): half roster strength (projected points from the
best starting lineup a team can actually field), half value. But this is
a snake draft, not an auction -- there's no $ spent, so "value" here means
pick-slot value instead of price: for each pick, how much later (positive)
or earlier (negative) than this year's real VOR rank a team got that
player, i.e. `pick_number - overall_rank`. A team that got a rank-90
player with pick 150 earned +60 of real value; reaching for a rank-90 guy
at pick 30 cost -60.

Keeper picks are excluded from the value calculation on purpose: a real
keeper's draft slot was locked in by last year's keeper cost, not
competitively earned this year, so grading it as a "value" pick would be
rewarding or punishing a decision that already happened. Keepers still
count toward roster/starting-lineup strength, since they're real rostered
players either way.
"""
from __future__ import annotations

import pandas as pd

from .value import FLEX_SLOTS_PER_TEAM, STARTERS

FLEX_ELIGIBLE = {"RB", "WR", "TE"}

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


def _optimal_lineup_points(team_df: pd.DataFrame, slots: dict, flex_n: int) -> float:
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
    total += flex_picks["projected_points"].sum()
    return total


def compute_needs(team_df: pd.DataFrame, slots: dict, flex_n: int) -> str:
    remaining = dict(slots)
    flex_remaining = flex_n
    for pos in team_df.sort_values("pick")["position"]:
        pos = str(pos).strip().upper()
        if remaining.get(pos, 0) > 0:
            remaining[pos] -= 1
        elif pos in FLEX_ELIGIBLE and flex_remaining > 0:
            flex_remaining -= 1
    open_dedicated = {pos: n for pos, n in remaining.items() if n > 0}
    parts = [f"{n} {pos}" if n > 1 else pos for pos, n in open_dedicated.items()]
    if flex_remaining > 0:
        parts.append(f"{flex_remaining} FLEX" if flex_remaining > 1 else "FLEX")
    return "needs " + ", ".join(parts) if parts else "starting lineup full"


def grade_draft(
    picks: pd.DataFrame,
    projections: pd.DataFrame,
    starting_slots: dict | None = None,
    flex_slots: int | None = None,
) -> pd.DataFrame:
    """picks: pick, team_name, player_name, position[, is_keeper].
    projections: player_name, projected_points, overall_rank (or vor).

    Returns one row per team, sorted best grade first: team_name,
    starting_points, roster_points, value_surplus, grade, best_value_name/
    delta, worst_value_name/delta, needs.
    """
    slots = dict(starting_slots or STARTERS)
    flex_n = flex_slots if flex_slots is not None else FLEX_SLOTS_PER_TEAM

    proj_cols = ["player_name", "projected_points", "overall_rank"]
    merged = picks.merge(projections[proj_cols], on="player_name", how="left")
    merged["projected_points"] = merged["projected_points"].fillna(0.0)
    merged["overall_rank"] = merged["overall_rank"].fillna(len(projections) + 1)
    if "is_keeper" not in merged.columns:
        merged["is_keeper"] = False
    merged["is_keeper"] = merged["is_keeper"].fillna(False)
    merged["value_delta"] = merged["pick"] - merged["overall_rank"]

    rows = []
    for team_name, team_df in merged.groupby("team_name"):
        team_df = team_df.reset_index(drop=True)
        starting_points = _optimal_lineup_points(team_df, slots, flex_n)
        roster_points = team_df["projected_points"].sum()

        live_df = team_df[~team_df["is_keeper"]]
        value_surplus = live_df["value_delta"].sum() if not live_df.empty else 0.0
        if not live_df.empty:
            best_value = live_df.loc[live_df["value_delta"].idxmax()]
            worst_value = live_df.loc[live_df["value_delta"].idxmin()]
        else:
            best_value = worst_value = pd.Series({"player_name": "--", "value_delta": 0.0})

        rows.append({
            "team_name": team_name,
            "starting_points": starting_points,
            "roster_points": roster_points,
            "value_surplus": value_surplus,
            "best_value_name": best_value["player_name"],
            "best_value_delta": best_value["value_delta"],
            "worst_value_name": worst_value["player_name"],
            "worst_value_delta": worst_value["value_delta"],
            "needs": compute_needs(team_df, slots, flex_n),
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
