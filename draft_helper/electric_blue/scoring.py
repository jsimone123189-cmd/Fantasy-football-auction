"""Electric Blue's real scoring rules, confirmed from the league's actual
Scoring & Settings page (pulled directly from Yahoo, league ID 172092 era --
see the Electric Blue project memory for the note on verifying this still
matches the current season's settings page).

Half-PPR, 1pt/25 pass yards (not Top Teamz's 1pt/50 or Rivals' 1pt/25 --
coincidentally the same rate as Rivals, but everything else differs), three-
tier stacking yardage milestone bonuses on ALL THREE of passing/rushing/
receiving yards (Top Teamz only has pass+rush bonuses; Rivals has none at
all), fully distance-tiered kicker scoring (not flat+bonus like Rivals),
and points-allowed-only DEF scoring (no yards-allowed tier, unlike Top
Teamz).
"""
from __future__ import annotations

import math

OFFENSE_SCORING = {
    "receptions": 0.5,
    "rush_yards": 0.1,
    "rush_td": 6,
    "rec_yards": 0.1,
    "rec_td": 6,
    "pass_yards": 0.04,
    "pass_td": 4,
    "interceptions": -1,
    "return_td": 6,
    "two_pt": 2,
    "fumbles_lost": -2,
    "offensive_fumble_return_td": 6,
}

# Stacking milestone bonuses -- a 520-yard passing game earns both the 300
# and 500 bonus (but not the 555 tier). All three yardage categories have
# their own three-tier bonus ladder in this league, confirmed real values.
PASS_YARD_BONUSES = [(300, 1), (500, 3), (555, 25)]
RUSH_YARD_BONUSES = [(100, 2), (200, 4), (297, 25)]
REC_YARD_BONUSES = [(100, 1), (200, 3), (337, 25)]
BONUS_CV = {"pass": 0.28, "rush": 0.42, "rec": 0.48}

DEF_SCORING = {
    "sack": 1,
    "interception": 2,
    "fumble_recovery": 2,
    "touchdown": 6,
    "safety": 2,
    "block_kick": 2,
}
POINTS_ALLOWED_TIERS = [
    (0, 10), (6, 7), (13, 4), (20, 1), (27, 0), (34, -1), (float("inf"), -4),
]


def score_offense(stats: dict) -> float:
    points = 0.0
    for key, rate in OFFENSE_SCORING.items():
        points += stats.get(key, 0.0) * rate
    return points


def _normal_survival(threshold: float, mean: float, sd: float) -> float:
    if sd <= 0:
        return 1.0 if mean > threshold else 0.0
    z = (threshold - mean) / (sd * math.sqrt(2))
    return 0.5 * (1 - math.erf(z))


def expected_milestone_bonus(games: float, pass_ypg: float = 0.0, rush_ypg: float = 0.0, rec_ypg: float = 0.0) -> float:
    if games <= 0:
        return 0.0
    per_game = 0.0
    for ypg, bonuses, cv_key in (
        (pass_ypg, PASS_YARD_BONUSES, "pass"),
        (rush_ypg, RUSH_YARD_BONUSES, "rush"),
        (rec_ypg, REC_YARD_BONUSES, "rec"),
    ):
        if ypg <= 0:
            continue
        sd = ypg * BONUS_CV[cv_key]
        for threshold, bonus in bonuses:
            per_game += _normal_survival(threshold, ypg, sd) * bonus
    return per_game * games


def _tiered_points(value: float, tiers: list[tuple[float, float]]) -> float:
    for threshold, points in tiers:
        if value <= threshold:
            return points
    return tiers[-1][1]


def score_defense(sacks: float, interceptions: float, fumble_rec: float, def_td: float, points_allowed_pg: float, games: float) -> float:
    points = (
        sacks * DEF_SCORING["sack"]
        + interceptions * DEF_SCORING["interception"]
        + fumble_rec * DEF_SCORING["fumble_recovery"]
        + def_td * DEF_SCORING["touchdown"]
    )
    points += _tiered_points(points_allowed_pg, POINTS_ALLOWED_TIERS) * games
    return points
