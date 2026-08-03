"""Your league's exact scoring rules, applied to a projected per-player stat
line to get fantasy points. This is the only place scoring math lives -- the
model in `model.py` only ever projects real stats (attempts, yards, TDs);
turning that into points is a pure lookup against this dict.

Confirmed directly from a screenshot of the league's real Yahoo scoring
settings page (Aug 2026) -- nothing in LEAGUE_SCORING below is an assumption
anymore:
    reception (0.5), pass_yard (1pt/50yds), pass_td (4), interception (-2),
    rush_yard (1pt/10yds), rush_td (6), rec_yard (1pt/10yds), rec_td (6),
    fumble_lost (-2), two_point (2)

The settings page also confirmed per-game yardage milestone bonuses that
don't fit a flat per-yard rate -- 6pts at 300 pass yards + 4pts at 500 (the
two stack), and 4pts at 100 rush yards + 2pts at 200 (also stack). Those are
scored separately by `expected_milestone_bonus` below: since the model
projects a *season average* yards/game rather than every individual game,
hitting a threshold is treated as a probability (assuming game-to-game
yardage is roughly normally distributed around that average) rather than an
all-or-nothing flag -- an every-week-average-250-yard passer clears 300 some
weeks and not others, and the expected bonus reflects that instead of
rounding to "never" or "always."
"""
from __future__ import annotations

import math

LEAGUE_SCORING = {
    "reception": 0.5,      # confirmed
    "rush_yard": 0.1,       # confirmed: 1 pt / 10 rush yards
    "rec_yard": 0.1,        # confirmed: 1 pt / 10 rec yards
    "pass_yard": 0.02,      # confirmed: 1 pt / 50 pass yards
    "pass_td": 4,           # confirmed
    "rush_td": 6,           # confirmed
    "rec_td": 6,            # confirmed
    "interception": -2,     # confirmed
    "fumble_lost": -2,      # confirmed
    "two_point": 2,         # confirmed
}

# Per-game yardage milestone bonuses (confirmed), applied as a stacking list
# of (threshold, bonus) pairs -- a 520-yard passing game earns both the 300
# and the 500 bonus.
PASS_YARD_BONUSES = [(300, 6), (500, 4)]
RUSH_YARD_BONUSES = [(100, 4), (200, 2)]

# Game-to-game coefficient of variation used only to spread the *season
# average* into a per-game distribution for the milestone-bonus estimate --
# real NFL yardage totals are noisier game-to-game for rushers (workload
# swings with game script) than for high-attempt-volume passers.
PASS_YARD_BONUS_CV = 0.28
RUSH_YARD_BONUS_CV = 0.42

ASSUMED_KEYS: set[str] = set()  # nothing left unconfirmed as of the Aug 2026 settings screenshot

SCORING_ASSUMPTION_NOTE = (
    "All scoring values (including the passing/rushing yardage milestone "
    "bonuses) are confirmed directly from the league's real Yahoo settings "
    "page as of Aug 2026 -- nothing here is an assumed default anymore."
)


def score_stat_line(stats: dict) -> float:
    """stats: any subset of rush_yards, rush_td, receptions, rec_yards,
    rec_td, pass_yards, pass_td, interceptions, fumbles_lost, two_pt.
    Missing keys are treated as zero. Does not include the yardage milestone
    bonuses -- see `expected_milestone_bonus` for those.
    """
    points = 0.0
    points += stats.get("rush_yards", 0.0) * LEAGUE_SCORING["rush_yard"]
    points += stats.get("rush_td", 0.0) * LEAGUE_SCORING["rush_td"]
    points += stats.get("receptions", 0.0) * LEAGUE_SCORING["reception"]
    points += stats.get("rec_yards", 0.0) * LEAGUE_SCORING["rec_yard"]
    points += stats.get("rec_td", 0.0) * LEAGUE_SCORING["rec_td"]
    points += stats.get("pass_yards", 0.0) * LEAGUE_SCORING["pass_yard"]
    points += stats.get("pass_td", 0.0) * LEAGUE_SCORING["pass_td"]
    points += stats.get("interceptions", 0.0) * LEAGUE_SCORING["interception"]
    points += stats.get("fumbles_lost", 0.0) * LEAGUE_SCORING["fumble_lost"]
    points += stats.get("two_pt", 0.0) * LEAGUE_SCORING["two_point"]
    return points


def _normal_survival(threshold: float, mean: float, sd: float) -> float:
    """P(X > threshold) for X ~ Normal(mean, sd)."""
    if sd <= 0:
        return 1.0 if mean > threshold else 0.0
    z = (threshold - mean) / (sd * math.sqrt(2))
    return 0.5 * (1 - math.erf(z))


def expected_milestone_bonus(games: float, pass_yards_per_game: float = 0.0, rush_yards_per_game: float = 0.0) -> float:
    """Expected season-total bonus points from the confirmed yardage
    milestones, given a projected per-game average and games played.
    """
    if games <= 0:
        return 0.0
    total_per_game = 0.0
    if pass_yards_per_game > 0:
        sd = pass_yards_per_game * PASS_YARD_BONUS_CV
        for threshold, bonus in PASS_YARD_BONUSES:
            total_per_game += _normal_survival(threshold, pass_yards_per_game, sd) * bonus
    if rush_yards_per_game > 0:
        sd = rush_yards_per_game * RUSH_YARD_BONUS_CV
        for threshold, bonus in RUSH_YARD_BONUSES:
            total_per_game += _normal_survival(threshold, rush_yards_per_game, sd) * bonus
    return total_per_game * games
