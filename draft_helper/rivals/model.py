"""Rivals FCL projection model.

Skill positions (QB/RB/WR/TE) reuse the same real, audited opportunity/
efficiency inputs as Top Teamz (`data/projections/inputs_2026.csv`) and the
same `TeamContext` environment multipliers -- it's the same real NFL player
pool and the same real 2026 team environments, so none of that research
needs to be redone. Only the scoring formula changes (see `scoring.py`):
full PPR instead of half-PPR, 1pt/25 pass yards instead of 1pt/50, and no
yardage milestone bonuses (Rivals' rules don't have them).

IDP (DL/LB/DB) and kicker are new positions Top Teamz doesn't have at all.
They're projected from real 2025 counting stats (`data/research/
idp_*_2026.csv`, `data/research/kickers_2026.csv`) turned into a per-game
rate, projected forward across `games_proj` games, and scored against
Rivals' IDP/kicker category scoring. Role-change notes from that research
(new starting job, lost a competition, scheme change, etc.) are folded in
as an explicit `role_mult` on the input row rather than silently -- see
`data/rivals/inputs_idp_2026.csv` header for how that number was chosen.
"""
from __future__ import annotations

from draft_helper.projections.team_context import TeamContext

from .scoring import score_idp, score_kicker, score_offense

GAMES_DEFAULT = 17.0

# Same risk framework as Top Teamz (see projections/model.py) -- floor/
# ceiling as a fraction of median points, driven by role security/injury
# history rather than pure box-score variance.
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


def _finalize(stats: dict, games: float, row, extra_drivers: list[str], score_fn) -> dict:
    median = round(score_fn(stats), 1)
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
        f"{rush_att_pg:.1f} carries/g x {ypc:.2f} YPC",
        f"{targets_pg:.1f} targets/g as receiver, full-PPR",
    ]
    return _finalize(stats, games, row, drivers, score_offense)


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
    rush_att = rush_att_pg * games
    rush_yards = rush_att * ypc
    rush_td = rush_att * rush_td_rate

    stats = dict(
        receptions=receptions, rec_yards=rec_yards, rec_td=rec_td,
        rush_yards=rush_yards, rush_td=rush_td,
    )
    drivers = [
        f"{targets_pg:.1f} targets/g, {catch_rate*100:.0f}% catch rate, {ypt:.1f} yds/target",
        "full-PPR: every catch worth 1.0 pt (vs 0.5 in Top Teamz)",
    ]
    return _finalize(stats, games, row, drivers, score_offense)


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
        f"{pass_att_pg:.1f} pass att/g x {ypa:.1f} YPA, {pass_td_rate*100:.1f}% TD rate "
        "(1pt/25 pass yds here, double Top Teamz's rate)",
        f"{rush_att_pg:.1f} rush att/g at {rush_ypc:.1f} YPC"
        if rush_att_pg >= 1.5 else "pocket passer, minimal rushing equity",
    ]
    return _finalize(stats, games, row, drivers, score_offense)


def project_idp(row) -> dict:
    """DL/LB/DB share one scoring category set. `row` supplies per-game
    rates (already adjusted for any known 2026 role change -- see the
    `role_mult` column applied when `data/rivals/inputs_idp_2026.csv` was
    built from the raw research) and `games_proj`.
    """
    games = _num(row, "games_proj", GAMES_DEFAULT)

    solo_pg = _num(row, "solo_pg")
    ast_pg = _num(row, "ast_pg")
    tfl_pg = _num(row, "tfl_pg")
    sack_pg = _num(row, "sack_pg")
    ff_pg = _num(row, "ff_pg")
    fr_pg = _num(row, "fr_pg")
    int_pg = _num(row, "int_pg")
    pd_pg = _num(row, "pd_pg")

    stats = dict(
        solo_tackles=solo_pg * games,
        ast_tackles=ast_pg * games,
        tfl=tfl_pg * games,
        sacks=sack_pg * games,
        forced_fumbles=ff_pg * games,
        fumble_recoveries=fr_pg * games,
        interceptions=int_pg * games,
        passes_defended=pd_pg * games,
    )
    drivers = [
        f"{solo_pg:.1f} solo + {ast_pg:.1f} ast tackles/g "
        f"({(solo_pg*1.5 + ast_pg*0.75):.1f} pts/g from tackle volume alone)",
        f"{tfl_pg:.2f} TFL/g, {sack_pg:.2f} sacks/g, {pd_pg:.2f} PD/g",
    ]
    role_note = _text(row, "role_note")
    if role_note:
        drivers.append(role_note)
    return _finalize(stats, games, row, drivers, score_idp)


def project_kicker(row) -> dict:
    games = _num(row, "games_proj", GAMES_DEFAULT)

    fg_made_pg = _num(row, "fg_made_pg")
    fg_40_49_pg = _num(row, "fg_40_49_pg")
    fg_50plus_pg = _num(row, "fg_50plus_pg")
    xp_made_pg = _num(row, "xp_made_pg")
    fg_missed_pg = _num(row, "fg_missed_pg")
    xp_missed_pg = _num(row, "xp_missed_pg")

    stats = dict(
        fg_made=fg_made_pg * games,
        fg_made_40_49=fg_40_49_pg * games,
        fg_made_50plus=fg_50plus_pg * games,
        xp_made=xp_made_pg * games,
        fg_missed=fg_missed_pg * games,
        xp_missed=xp_missed_pg * games,
    )
    drivers = [
        f"{fg_made_pg:.2f} FG made/g ({fg_40_49_pg:.2f} from 40-49, {fg_50plus_pg:.2f} from 50+)",
        f"{xp_made_pg:.2f} XP made/g",
    ]
    return _finalize(stats, games, row, drivers, score_kicker)


SKILL_PROJECTORS = {
    "RB": project_rb,
    "WR": project_wr_te,
    "TE": project_wr_te,
    "QB": project_qb,
}
