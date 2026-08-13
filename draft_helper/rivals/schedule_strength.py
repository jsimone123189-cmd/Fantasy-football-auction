"""Weeks 4-8 vs. weeks 9-12 schedule strength for Rivals FCL.

Rivals' scored season splits into two very different phases (see build.py):
group stage (weeks 4-8, floor matters) and single-elimination knockout
(weeks 9-12, ceiling matters, and this is what a team is actually built
for). This module supplies the real-schedule half of that split -- who
each team's offense actually plays in each phase, and how tough those
opponents' defenses project to be -- sourced from:

  - data/research/schedule_2026.csv: each team's real 2026 opponent for
    weeks 4-12, gathered via live web research (Aug 2026) and cross-
    validated against every bye week in data/research/bye_weeks_2026.csv
    (all 32 matched exactly).
  - data/research/defense_strength_2026.csv: a real, sourced (not
    fabricated) 3-tier run-defense/pass-defense read for the ~19 teams
    with a clear enough 2026 preseason signal one way or the other;
    every other team defaults to neutral rather than guessing.

RB value is adjusted by opponents' run-defense tier; QB/WR/TE value is
adjusted by opponents' pass-defense tier. IDP/K aren't adjusted here --
matchup difficulty for tackle volume or kicking opportunities isn't
something reliable, sourced data exists for at this fidelity, so those
positions get a neutral (1.0) multiplier rather than a fabricated one.
"""
from __future__ import annotations

import os

import pandas as pd

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCHEDULE_PATH = os.path.join(BASE_DIR, "data", "research", "schedule_2026.csv")
DEFENSE_PATH = os.path.join(BASE_DIR, "data", "research", "defense_strength_2026.csv")

EARLY_WEEKS = range(4, 9)    # group stage
LATE_WEEKS = range(9, 13)    # knockout bracket

TIER_MULT = {"tough": 0.92, "weak": 1.08, "neutral": 1.0}

# QB includes here because Rivals scores QBs on passing production, which
# runs into the same pass defenses WR/TE face.
PASS_FACING_POSITIONS = {"QB", "WR", "TE"}
RUN_FACING_POSITIONS = {"RB"}


def load_schedule(path: str = SCHEDULE_PATH) -> dict:
    if not os.path.exists(path):
        return {}
    df = pd.read_csv(path)
    schedule = {}
    for _, row in df.iterrows():
        schedule[row["team"]] = {
            week: row[f"week_{week}"] for week in range(4, 13)
        }
    return schedule


def load_defense_strength(path: str = DEFENSE_PATH) -> dict:
    if not os.path.exists(path):
        return {}
    df = pd.read_csv(path)
    strength = {}
    for _, row in df.iterrows():
        strength[row["team"]] = {"run": row["run_tier"], "pass": row["pass_tier"]}
    return strength


def _relevant_tier_key(position: str) -> str | None:
    if position in RUN_FACING_POSITIONS:
        return "run"
    if position in PASS_FACING_POSITIONS:
        return "pass"
    return None  # IDP/K: no matchup adjustment, stays neutral


def week_range_multiplier(
    team: str,
    position: str,
    week_range,
    schedule: dict,
    defense: dict,
) -> float:
    """Average SOS multiplier across the non-bye weeks in `week_range` for
    `team`'s opponents, from `position`'s point of view. Returns 1.0
    (neutral) if the team/position/schedule data isn't available -- this
    only ever nudges value, it never invents a matchup.
    """
    tier_key = _relevant_tier_key(position)
    if tier_key is None:
        return 1.0
    team_sched = schedule.get(team)
    if not team_sched:
        return 1.0

    mults = []
    for week in week_range:
        opponent = team_sched.get(week)
        if not opponent or opponent == "BYE":
            continue
        opp_strength = defense.get(opponent, {})
        tier = opp_strength.get(tier_key, "neutral")
        mults.append(TIER_MULT.get(tier, 1.0))

    if not mults:
        return 1.0
    return sum(mults) / len(mults)
