"""Rivals FCL's real scoring rules (Fantrax, confirmed from the league's
"League Rules Summary" screenshots, Aug 2026). This is a completely
different ruleset from the Top Teamz league in `draft_helper/projections/
scoring.py` -- full PPR instead of half-PPR, 1pt/25 pass yards instead of
1pt/50, no yardage milestone bonuses, and a full IDP + kicker category set
that Top Teamz doesn't have at all.

Kept as its own module (not merged into `projections/scoring.py`) because
these two leagues score real stat lines differently enough that sharing a
dict would risk one league's edit silently breaking the other.
"""
from __future__ import annotations

OFFENSE_SCORING = {
    "reception": 1.0,        # confirmed: full PPR
    "rush_yard": 0.1,         # confirmed: 1 pt / 10 rush yards
    "rec_yard": 0.1,          # confirmed: 1 pt / 10 rec yards
    "pass_yard": 0.04,        # confirmed: 1 pt / 25 pass yards
    "pass_td": 4,             # confirmed
    "rush_td": 6,             # confirmed
    "rec_td": 6,              # confirmed
    "interception": -2,       # confirmed: interceptions thrown
    "fumble_lost": -2,        # confirmed
    "fumble_return_td": 6,    # confirmed: offensive fumble recovered for TD
    "two_point": 2,           # confirmed
    "return_td": 6,           # confirmed: kick/punt return TD
}

# Individual Defensive Player scoring -- identical category set applies to
# DL, LB, and DB alike (Fantrax scores IDP by stat category, not position).
# Tackle-heavy: solo+assist alone make a three-down LB or box safety
# competitive with splash-play-only pass rushers.
IDP_SCORING = {
    "solo_tackle": 1.5,             # confirmed
    "assisted_tackle": 0.75,        # confirmed
    "tackle_for_loss": 2,           # confirmed (in addition to the solo/assist points for that tackle)
    "sack": 4,                      # confirmed
    "forced_fumble": 4,             # confirmed
    "fumble_recovery": 2,           # confirmed
    "interception": 5,              # confirmed
    "pass_defended": 2,             # confirmed
    "defensive_td": 6,              # confirmed
    "safety": 2,                    # confirmed
    "blocked_field_goal": 3,        # confirmed
    "blocked_extra_point": 1,       # confirmed
    "blocked_xp_return_td": 2,      # confirmed
}

KICKER_SCORING = {
    "xp_made": 1,           # confirmed
    "fg_made": 1,            # confirmed: flat, any distance
    "fg_made_40_49": 1,      # confirmed: EXTRA point on top of fg_made for a 40-49 yd make
    "fg_made_50plus": 2,     # confirmed: EXTRA points on top of fg_made for a 50+ yd make
    "xp_missed": -1,         # confirmed
    "fg_missed": -1,         # confirmed
}

SCORING_ASSUMPTION_NOTE = (
    "All scoring values confirmed directly from the Rivals FCL Fantrax "
    "league rules summary (screenshots, Aug 2026) -- full PPR, 1pt/25 pass "
    "yards, no yardage milestone bonuses, full IDP tackle/sack/turnover "
    "categories, and distance-tiered kicker scoring."
)


def score_offense(stats: dict) -> float:
    """stats: any subset of rush_yards, rush_td, receptions, rec_yards,
    rec_td, pass_yards, pass_td, interceptions, fumbles_lost,
    fumble_return_td, two_pt, return_td. Missing keys are treated as zero.
    """
    points = 0.0
    points += stats.get("rush_yards", 0.0) * OFFENSE_SCORING["rush_yard"]
    points += stats.get("rush_td", 0.0) * OFFENSE_SCORING["rush_td"]
    points += stats.get("receptions", 0.0) * OFFENSE_SCORING["reception"]
    points += stats.get("rec_yards", 0.0) * OFFENSE_SCORING["rec_yard"]
    points += stats.get("rec_td", 0.0) * OFFENSE_SCORING["rec_td"]
    points += stats.get("pass_yards", 0.0) * OFFENSE_SCORING["pass_yard"]
    points += stats.get("pass_td", 0.0) * OFFENSE_SCORING["pass_td"]
    points += stats.get("interceptions", 0.0) * OFFENSE_SCORING["interception"]
    points += stats.get("fumbles_lost", 0.0) * OFFENSE_SCORING["fumble_lost"]
    points += stats.get("fumble_return_td", 0.0) * OFFENSE_SCORING["fumble_return_td"]
    points += stats.get("two_pt", 0.0) * OFFENSE_SCORING["two_point"]
    points += stats.get("return_td", 0.0) * OFFENSE_SCORING["return_td"]
    return points


def score_idp(stats: dict) -> float:
    """stats: any subset of solo_tackles, ast_tackles, tfl, sacks,
    forced_fumbles, fumble_recoveries, interceptions, passes_defended,
    def_td, safeties, blocked_fg, blocked_xp, blocked_xp_return_td.
    """
    points = 0.0
    points += stats.get("solo_tackles", 0.0) * IDP_SCORING["solo_tackle"]
    points += stats.get("ast_tackles", 0.0) * IDP_SCORING["assisted_tackle"]
    points += stats.get("tfl", 0.0) * IDP_SCORING["tackle_for_loss"]
    points += stats.get("sacks", 0.0) * IDP_SCORING["sack"]
    points += stats.get("forced_fumbles", 0.0) * IDP_SCORING["forced_fumble"]
    points += stats.get("fumble_recoveries", 0.0) * IDP_SCORING["fumble_recovery"]
    points += stats.get("interceptions", 0.0) * IDP_SCORING["interception"]
    points += stats.get("passes_defended", 0.0) * IDP_SCORING["pass_defended"]
    points += stats.get("def_td", 0.0) * IDP_SCORING["defensive_td"]
    points += stats.get("safeties", 0.0) * IDP_SCORING["safety"]
    points += stats.get("blocked_fg", 0.0) * IDP_SCORING["blocked_field_goal"]
    points += stats.get("blocked_xp", 0.0) * IDP_SCORING["blocked_extra_point"]
    points += stats.get("blocked_xp_return_td", 0.0) * IDP_SCORING["blocked_xp_return_td"]
    return points


def score_kicker(stats: dict) -> float:
    """stats: any subset of xp_made, fg_made, fg_made_40_49, fg_made_50plus,
    xp_missed, fg_missed. fg_made_40_49/fg_made_50plus are the EXTRA points
    on top of the flat fg_made point for those distance-bucket makes.
    """
    points = 0.0
    points += stats.get("xp_made", 0.0) * KICKER_SCORING["xp_made"]
    points += stats.get("fg_made", 0.0) * KICKER_SCORING["fg_made"]
    points += stats.get("fg_made_40_49", 0.0) * KICKER_SCORING["fg_made_40_49"]
    points += stats.get("fg_made_50plus", 0.0) * KICKER_SCORING["fg_made_50plus"]
    points += stats.get("xp_missed", 0.0) * KICKER_SCORING["xp_missed"]
    points += stats.get("fg_missed", 0.0) * KICKER_SCORING["fg_missed"]
    return points
