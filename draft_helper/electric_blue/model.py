"""Electric Blue projection model. Skill positions (QB/RB/WR/TE) reuse the
same real opportunity/efficiency inputs as Top Teamz and Rivals FCL (same
real players, same real 2026 team environments) -- only the scoring changes.
No kicker this season (confirmed live during the 2026 draft -- this league
dropped the K slot entirely). DEF reuses Top Teamz's team-quality tier model
(draft_helper.projections.def_model), rescored under Electric Blue's
points-allowed-only DEF rules (no yards-allowed tier here).
"""
from __future__ import annotations

from draft_helper.projections.def_model import TIERS, _win_total_tier
from draft_helper.projections.team_context import TeamContext

from .scoring import expected_milestone_bonus, score_defense, score_offense

GAMES_DEFAULT = 17.0

RISK_BANDS = {
    "low": (0.85, 1.18),
    "medium": (0.75, 1.28),
    "high": (0.63, 1.42),
    "very_high": (0.50, 1.60),
}


def _num(row, key, default=0.0):
    val = row.get(key, default)
    try:
        if val is None or (isinstance(val, float) and val != val):
            return default
        return float(val)
    except (TypeError, ValueError):
        return default


def _text(row, key, default=""):
    val = row.get(key, default)
    if val is None:
        return default
    try:
        if isinstance(val, float) and val != val:
            return default
    except TypeError:
        pass
    val = str(val).strip()
    return val if val and val.lower() != "nan" else default


def _risk_band(row):
    tier = _text(row, "risk_tier", "medium").lower()
    return RISK_BANDS.get(tier, RISK_BANDS["medium"]), tier


def _finalize(median: float, row, drivers: list[str]) -> dict:
    (floor_mult, ceil_mult), risk_tier = _risk_band(row)
    return {
        "projected_points": round(median, 1),
        "floor": round(median * floor_mult, 1),
        "ceiling": round(median * ceil_mult, 1),
        "risk_tier": risk_tier,
        "drivers": drivers,
    }


def project_rb(row, team: TeamContext) -> dict:
    games = _num(row, "games_proj", GAMES_DEFAULT)
    rush_att_pg = _num(row, "rush_att_pg") * team.run_funnel_mult * team.rb_gamescript_mult
    ypc = _num(row, "ypc") * (1 + 0.4 * (team.ol_mult - 1))
    rush_td_rate = _num(row, "rush_td_rate") * team.scoring_mult
    targets_pg = _num(row, "targets_pg") * team.pass_funnel_mult
    catch_rate = _num(row, "catch_rate", 0.72)
    ypt = _num(row, "ypt")
    rec_td_rate = _num(row, "rec_td_rate") * team.scoring_mult

    rush_yards = rush_att_pg * ypc * games
    rush_td = rush_att_pg * rush_td_rate * games
    targets = targets_pg * games
    receptions = targets * catch_rate
    rec_yards = targets * ypt
    rec_td = targets * rec_td_rate

    stats = dict(rush_yards=rush_yards, rush_td=rush_td, receptions=receptions, rec_yards=rec_yards, rec_td=rec_td)
    bonus = expected_milestone_bonus(games, rush_ypg=rush_att_pg * ypc, rec_ypg=targets_pg * ypt)
    median = score_offense(stats) + bonus
    drivers = [f"{rush_att_pg:.1f} carries/g x {ypc:.2f} YPC", f"{targets_pg:.1f} targets/g, half-PPR"]
    if bonus >= 3:
        drivers.append(f"+{bonus:.0f} pts from yardage milestone bonuses")
    return _finalize(median, row, drivers)


def project_wr_te(row, team: TeamContext) -> dict:
    games = _num(row, "games_proj", GAMES_DEFAULT)
    targets_pg = _num(row, "targets_pg") * team.pass_funnel_mult * team.pass_gamescript_mult
    catch_rate = _num(row, "catch_rate", 0.62)
    ypt = _num(row, "ypt")
    td_rate = _num(row, "td_rate_per_target") * team.scoring_mult
    rush_att_pg = _num(row, "rush_att_pg")
    ypc = _num(row, "ypc")
    rush_td_rate = _num(row, "rush_td_rate")

    targets = targets_pg * games
    receptions = targets * catch_rate
    rec_yards = targets * ypt
    rec_td = targets * td_rate
    rush_yards = rush_att_pg * ypc * games
    rush_td = rush_att_pg * rush_td_rate * games

    stats = dict(receptions=receptions, rec_yards=rec_yards, rec_td=rec_td, rush_yards=rush_yards, rush_td=rush_td)
    bonus = expected_milestone_bonus(games, rec_ypg=targets_pg * ypt, rush_ypg=rush_att_pg * ypc)
    median = score_offense(stats) + bonus
    drivers = [f"{targets_pg:.1f} targets/g, {catch_rate*100:.0f}% catch rate, {ypt:.1f} yds/target"]
    if bonus >= 3:
        drivers.append(f"+{bonus:.0f} pts from yardage milestone bonuses")
    return _finalize(median, row, drivers)


def project_qb(row, team: TeamContext) -> dict:
    games = _num(row, "games_proj", GAMES_DEFAULT)
    pass_att_pg = _num(row, "pass_att_pg") * team.pass_funnel_mult * team.pass_gamescript_mult
    ypa = _num(row, "pass_ypa")
    pass_td_rate = _num(row, "pass_td_rate") * team.scoring_mult
    int_rate = _num(row, "int_rate")
    rush_att_pg = _num(row, "qb_rush_att_pg")
    rush_ypc = _num(row, "qb_rush_ypc")
    rush_td_rate = _num(row, "qb_rush_td_rate") * team.scoring_mult

    pass_yards = pass_att_pg * ypa * games
    pass_td = pass_att_pg * pass_td_rate * games
    interceptions = pass_att_pg * int_rate * games
    rush_yards = rush_att_pg * rush_ypc * games
    rush_td = rush_att_pg * rush_td_rate * games

    stats = dict(pass_yards=pass_yards, pass_td=pass_td, interceptions=interceptions, rush_yards=rush_yards, rush_td=rush_td)
    bonus = expected_milestone_bonus(games, pass_ypg=pass_att_pg * ypa, rush_ypg=rush_att_pg * rush_ypc)
    median = score_offense(stats) + bonus
    drivers = [
        f"{pass_att_pg:.1f} pass att/g x {ypa:.1f} YPA, {pass_td_rate*100:.1f}% TD rate (1pt/25 pass yds here)",
        f"{rush_att_pg:.1f} rush att/g at {rush_ypc:.1f} YPC" if rush_att_pg >= 1.5 else "pocket passer, minimal rushing equity",
    ]
    if bonus >= 3:
        drivers.append(f"+{bonus:.0f} pts from yardage milestone bonuses")
    return _finalize(median, row, drivers)


def project_defense(team_name: str, win_total: float) -> dict:
    tier_name = _win_total_tier(win_total)
    tier = TIERS[tier_name]
    games = GAMES_DEFAULT
    median = score_defense(
        sacks=tier["sacks_pg"] * games,
        interceptions=tier["int_pg"] * games,
        fumble_rec=tier["fum_rec_pg"] * games,
        def_td=tier["def_td_per_season"],
        points_allowed_pg=tier["pts_allowed_pg"],
        games=games,
    )
    drivers = [
        f"{tier_name.capitalize()}-tier defense ({win_total:.1f}-win Vegas total)",
        f"~{tier['sacks_pg']:.1f} sacks/g, ~{tier['int_pg']:.2f} INT/g, ~{tier['pts_allowed_pg']:.1f} pts allowed/g "
        "(no yards-allowed component in this league's DEF rules, unlike Top Teamz)",
    ]
    row = {"risk_tier": "medium"}
    return _finalize(median, row, drivers)


SKILL_PROJECTORS = {"RB": project_rb, "WR": project_wr_te, "TE": project_wr_te, "QB": project_qb}
