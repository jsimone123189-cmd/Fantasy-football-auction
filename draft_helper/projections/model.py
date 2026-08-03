"""The projection model itself (spec Steps 1, 2, 5, 6, 7).

Every player is projected from a real stat line -- attempts, targets,
catch rate, yards/touch, TD rate -- not from a ranking. Step-by-step:

1. Opportunity (`*_pg` fields in the per-player input row): raw
   volume -- carries, targets, expected snaps -- before any adjustment.
2. Efficiency (`ypc`, `ypt`, `catch_rate`, `*_td_rate` fields): the
   player's own per-touch production rate, informed by real career/2025
   role and skill (explosiveness, catch radius, YAC, etc.) rather than a
   league-average rate.
3+4+5. Team environment, betting markets, and personnel changes are folded
   into the opportunity/efficiency numbers themselves by whoever populated
   the input row (see data/projections/inputs_2026.csv "*_note" columns for
   the specific driver), then re-applied here as the TeamContext
   multipliers (see team_context.py) so the effect is visible and
   traceable, not baked in silently.
6. Game script: `TeamContext.rb_gamescript_mult` / `.pass_gamescript_mult`,
   derived from Vegas win total, tilt RB volume vs. pass volume based on how
   often that team plays with a lead vs. from behind.
7. Risk: `risk_tier` on the input row selects a floor/ceiling band (roughly
   20th/80th percentile) applied around the median -- see RISK_BANDS.

Output of every project_* function is a dict of real projected counting
stats (so the explanation can show "14.2 carries/g" rather than an opaque
number) plus the three fantasy-point numbers (floor/median/ceiling) scored
against the league's actual scoring rules (scoring.py).
"""
from __future__ import annotations

from .scoring import score_stat_line
from .team_context import TeamContext

GAMES_DEFAULT = 17.0

# Floor/ceiling as a fraction of median points -- roughly 20th/80th
# percentile outcomes given the player's boom/bust profile. "low" = a bell-cow
# workhorse or alpha target-earner with no committee/injury/role threat;
# "very_high" = rookies with no NFL track record, committee backfields, or
# players with a live injury/suspension question mark.
RISK_BANDS = {
    "low": (0.85, 1.18),
    "medium": (0.75, 1.28),
    "high": (0.63, 1.42),
    "very_high": (0.50, 1.60),
}


def _num(row, key, default=0.0):
    val = row.get(key, default)
    try:
        if val is None or (isinstance(val, float) and val != val):  # NaN
            return default
        return float(val)
    except (TypeError, ValueError):
        return default


def _text(row, key, default=""):
    val = row.get(key, default)
    if val is None:
        return default
    try:
        if isinstance(val, float) and val != val:  # NaN
            return default
    except TypeError:
        pass
    val = str(val).strip()
    return val if val and val.lower() != "nan" else default


def _risk_band(row):
    tier = _text(row, "risk_tier", "medium").lower()
    return RISK_BANDS.get(tier, RISK_BANDS["medium"]), tier


def _finalize(stats: dict, games: float, row, extra_drivers: list[str]):
    median = round(score_stat_line(stats), 1)
    (floor_mult, ceil_mult), risk_tier = _risk_band(row)
    return {
        "games_proj": round(games, 1),
        **{k: round(v, 1) for k, v in stats.items()},
        "projected_points": median,
        "floor": round(median * floor_mult, 1),
        "ceiling": round(median * ceil_mult, 1),
        "risk_tier": risk_tier,
        "drivers": extra_drivers,
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

    rush_att = rush_att_pg * games
    rush_yards = rush_att * ypc
    rush_td = rush_att * rush_td_rate
    targets = targets_pg * games
    receptions = targets * catch_rate
    rec_yards = targets * ypt
    rec_td = targets * rec_td_rate

    stats = dict(
        rush_yards=rush_yards, rush_td=rush_td,
        receptions=receptions, rec_yards=rec_yards, rec_td=rec_td,
    )
    drivers = [
        f"{rush_att_pg:.1f} carries/g ({_num(row,'rush_att_pg'):.1f} baseline x "
        f"{team.run_funnel_mult:.2f} scheme/OL x {team.rb_gamescript_mult:.2f} game-script)",
        f"{ypc:.2f} YPC efficiency",
        f"{targets_pg:.1f} targets/g as receiver",
    ]
    return _finalize(stats, games, row, drivers)


def project_wr_te(row, team: TeamContext) -> dict:
    games = _num(row, "games_proj", GAMES_DEFAULT)

    targets_pg = _num(row, "targets_pg") * team.pass_funnel_mult * team.pass_gamescript_mult
    catch_rate = _num(row, "catch_rate", 0.62)
    ypt = _num(row, "ypt")
    td_rate = _num(row, "td_rate_per_target") * team.scoring_mult

    rush_att_pg = _num(row, "rush_att_pg")  # jet-sweep/gadget WR touches, usually ~0
    ypc = _num(row, "ypc")
    rush_td_rate = _num(row, "rush_td_rate")

    targets = targets_pg * games
    receptions = targets * catch_rate
    rec_yards = targets * ypt
    rec_td = targets * td_rate
    rush_att = rush_att_pg * games
    rush_yards = rush_att * ypc
    rush_td = rush_att * rush_td_rate

    stats = dict(
        receptions=receptions, rec_yards=rec_yards, rec_td=rec_td,
        rush_yards=rush_yards, rush_td=rush_td,
    )
    drivers = [
        f"{targets_pg:.1f} targets/g ({_num(row,'targets_pg'):.1f} baseline x "
        f"{team.pass_funnel_mult:.2f} scheme/pace x {team.pass_gamescript_mult:.2f} game-script)",
        f"{catch_rate*100:.0f}% catch rate, {ypt:.1f} yds/target",
    ]
    return _finalize(stats, games, row, drivers)


def project_qb(row, team: TeamContext) -> dict:
    games = _num(row, "games_proj", GAMES_DEFAULT)

    pass_att_pg = _num(row, "pass_att_pg") * team.pass_funnel_mult * team.pass_gamescript_mult
    comp_pct = _num(row, "comp_pct", 0.64)
    ypa = _num(row, "pass_ypa")
    pass_td_rate = _num(row, "pass_td_rate") * team.scoring_mult
    int_rate = _num(row, "int_rate")

    rush_att_pg = _num(row, "qb_rush_att_pg")
    rush_ypc = _num(row, "qb_rush_ypc")
    rush_td_rate = _num(row, "qb_rush_td_rate") * team.scoring_mult

    pass_att = pass_att_pg * games
    pass_yards = pass_att * ypa
    pass_td = pass_att * pass_td_rate
    interceptions = pass_att * int_rate
    rush_att = rush_att_pg * games
    rush_yards = rush_att * rush_ypc
    rush_td = rush_att * rush_td_rate

    stats = dict(
        pass_yards=pass_yards, pass_td=pass_td, interceptions=interceptions,
        rush_yards=rush_yards, rush_td=rush_td,
    )
    drivers = [
        f"{pass_att_pg:.1f} pass att/g x {ypa:.1f} YPA, {pass_td_rate*100:.1f}% TD rate",
        f"{rush_att_pg:.1f} rush att/g at {rush_ypc:.1f} YPC ({rush_td_rate*100:.1f}% rush-TD rate)"
        if rush_att_pg >= 1.5 else "pocket passer, minimal rushing equity",
    ]
    return _finalize(stats, games, row, drivers)


PROJECTORS = {
    "RB": project_rb,
    "WR": project_wr_te,
    "TE": project_wr_te,
    "QB": project_qb,
}
