"""Your league's exact scoring rules, applied to a projected per-player stat
line to get fantasy points. This is the only place scoring math lives -- the
model in `model.py` only ever projects real stats (attempts, yards, TDs);
turning that into points is a pure lookup against this dict.

Confirmed directly from the league (half-PPR, no kicker, standard TD split):
    reception, pass_td, rush_td, rec_td

Not yet confirmed against the real Yahoo scoring settings page -- assumed as
Yahoo defaults per league owner's explicit instruction, and surfaced in every
player's explanation via `ASSUMED_KEYS` so a settings correction is a one-line
fix, not a re-derivation:
    pass_yard, rush_yard, rec_yard, interception, fumble_lost, two_point
"""
from __future__ import annotations

LEAGUE_SCORING = {
    "reception": 0.5,      # confirmed: half-PPR
    "rush_yard": 0.1,      # assumed: 1 pt / 10 rush yards
    "rec_yard": 0.1,       # assumed: 1 pt / 10 rec yards
    "pass_yard": 0.04,     # assumed: 1 pt / 25 pass yards
    "pass_td": 4,          # confirmed
    "rush_td": 6,          # confirmed
    "rec_td": 6,           # confirmed
    "interception": -2,    # assumed: standard Yahoo default
    "fumble_lost": -2,     # assumed: standard Yahoo default
    "two_point": 2,        # assumed: standard Yahoo default
}

ASSUMED_KEYS = {"pass_yard", "rush_yard", "rec_yard", "interception", "fumble_lost", "two_point"}

SCORING_ASSUMPTION_NOTE = (
    "Yardage-bonus, INT, fumble, and 2pt values are assumed Yahoo defaults "
    "(not yet confirmed against the league's actual settings page); "
    "reception (0.5), passing TD (4pt), and rushing/receiving TD (6pt) are "
    "confirmed."
)


def score_stat_line(stats: dict) -> float:
    """stats: any subset of rush_yards, rush_td, receptions, rec_yards,
    rec_td, pass_yards, pass_td, interceptions, fumbles_lost, two_pt.
    Missing keys are treated as zero.
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
