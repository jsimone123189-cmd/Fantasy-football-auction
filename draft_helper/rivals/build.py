"""Builds data/rivals/2026.csv -- the full Rivals FCL projection set
(QB/RB/WR/TE/DL/LB/DB/K) with VOR-based snake-draft ranking.

Run as: python -m draft_helper.rivals.build

Reads:
  - data/projections/inputs_2026.csv       (skill-position opportunity/
    efficiency inputs -- shared with Top Teamz, same real player pool)
  - data/research/team_context_2026.csv     (shared team environment research)
  - data/rivals/inputs_idp_2026.csv         (DL/LB/DB per-game rate inputs,
    built from data/research/idp_{dl,lb,db}_2026.csv)
  - data/rivals/inputs_kicker_2026.csv      (kicker per-game rate inputs,
    built from data/research/kickers_2026.csv)
  - data/research/schedule_2026.csv         (each team's real weeks 4-12
    opponents)
  - data/research/defense_strength_2026.csv (real, sourced run/pass
    defense tiers for the teams with a clear 2026 signal)

Writes:
  - data/rivals/2026.csv with columns player_name, position, nfl_team,
    projected_points, floor, ceiling, risk_tier, points_early, points_late,
    pos_rank, vor, overall_rank, vor_round, explanation, bye_week,
    market_overall_pick, market_round, market_verified.
    projected_points/floor/ceiling are the honest real-points projection
    across Rivals' full scored season (weeks 4-12); vor/overall_rank/
    vor_round additionally weight weeks 9-12 (the knockout bracket) more
    heavily via LATE_WEIGHT below, per explicit request to prioritize
    "good enough" weeks 4-8 and "best" weeks 9-12 -- see
    _rescale_to_scored_weeks() and the vor blend in build().
    market_round/market_overall_pick are real, sourced consensus ADP
    (data/research/market_adp_2026.csv), kept deliberately separate from
    vor_round -- see attach_market_adp()'s docstring for why the two must
    never be conflated. market_verified=False means this player hasn't
    been checked against real consensus and market_round is unset; do not
    treat vor_round as a stand-in for it.
    tier/tier_dropoff/tier_market_rounds are the real, position-relative
    cliff analysis -- see compute_position_tiers()/compute_tier_dropoff()
    in value.py for why a flat overall rank hides this. tier_dropoff is
    the real points lost falling from this player's tier to the next
    tier down at the same position; tier_market_rounds is the real,
    verified consensus-ADP round span covering *that next tier* (the
    matched "how much runway before the fallback is gone too" signal,
    blank where nothing in the fallback tier has been market-verified).
"""
from __future__ import annotations

import os

import pandas as pd

from draft_helper.projections.team_context import DEFAULT_IMPLIED_PPG, TeamContext, load_team_contexts

from .model import SKILL_PROJECTORS, project_idp, project_kicker
from .schedule_strength import (
    DEFENSE_PATH as SCHEDULE_STRENGTH_DEFENSE_PATH,
    EARLY_WEEKS,
    LATE_WEEKS,
    SCHEDULE_PATH as SCHEDULE_STRENGTH_SCHEDULE_PATH,
    load_defense_strength,
    load_schedule,
    week_range_multiplier,
)
from .teams import idp_bucket, to_nickname
from .value import (
    apply_bell_cow_scarcity,
    compute_position_tiers,
    compute_tier_dropoff,
    compute_vor,
    position_vor,
    rank_from_vor,
)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SKILL_INPUTS_PATH = os.path.join(BASE_DIR, "data", "projections", "inputs_2026.csv")
TEAM_CONTEXT_PATH = os.path.join(BASE_DIR, "data", "research", "team_context_2026.csv")
IDP_INPUTS_PATH = os.path.join(BASE_DIR, "data", "rivals", "inputs_idp_2026.csv")
KICKER_INPUTS_PATH = os.path.join(BASE_DIR, "data", "rivals", "inputs_kicker_2026.csv")
BYE_WEEKS_PATH = os.path.join(BASE_DIR, "data", "research", "bye_weeks_2026.csv")
SCHEDULE_PATH = SCHEDULE_STRENGTH_SCHEDULE_PATH
DEFENSE_STRENGTH_PATH = SCHEDULE_STRENGTH_DEFENSE_PATH
MARKET_ADP_PATH = os.path.join(BASE_DIR, "data", "research", "market_adp_2026.csv")
OUT_PATH = os.path.join(BASE_DIR, "data", "rivals", "2026.csv")


def _explain(row_result: dict, extra: str = "") -> str:
    parts = list(row_result.get("drivers", []))
    if extra:
        parts.append(extra)
    return " | ".join(parts)


def build(
    skill_inputs_path=SKILL_INPUTS_PATH,
    team_context_path=TEAM_CONTEXT_PATH,
    idp_inputs_path=IDP_INPUTS_PATH,
    kicker_inputs_path=KICKER_INPUTS_PATH,
    bye_weeks_path=BYE_WEEKS_PATH,
    schedule_path=SCHEDULE_PATH,
    defense_strength_path=DEFENSE_STRENGTH_PATH,
) -> pd.DataFrame:
    rows = []

    contexts = load_team_contexts(team_context_path) if os.path.exists(team_context_path) else {}
    league_avg_ppg = (
        pd.Series([c.implied_ppg for c in contexts.values()]).mean()
        if contexts else DEFAULT_IMPLIED_PPG
    )

    if os.path.exists(skill_inputs_path):
        skill_inputs = pd.read_csv(skill_inputs_path)
        for _, row in skill_inputs.iterrows():
            position = str(row["position"]).strip().upper()
            projector = SKILL_PROJECTORS.get(position)
            if projector is None:
                continue
            team_name = str(row.get("nfl_team", "")).strip()
            team_ctx = contexts.get(team_name) or TeamContext(None, league_avg_ppg)
            result = projector(row, team_ctx)
            rows.append({
                "player_name": row["player_name"],
                "position": position,
                "nfl_team": team_name,
                "projected_points": result["projected_points"],
                "floor": result["floor"],
                "ceiling": result["ceiling"],
                "risk_tier": result["risk_tier"],
                "explanation": _explain(result),
                "rush_att_pg": row.get("rush_att_pg"),
            })

    if os.path.exists(idp_inputs_path):
        idp_inputs = pd.read_csv(idp_inputs_path)
        for _, row in idp_inputs.iterrows():
            result = project_idp(row)
            sub_position = str(row["position"]).strip().upper()
            rows.append({
                "player_name": row["player_name"],
                "position": idp_bucket(sub_position),
                "nfl_team": to_nickname(row.get("nfl_team", "")),
                "projected_points": result["projected_points"],
                "floor": result["floor"],
                "ceiling": result["ceiling"],
                "risk_tier": result["risk_tier"],
                "explanation": _explain(result, extra=f"listed as {sub_position}"),
            })

    if os.path.exists(kicker_inputs_path):
        kicker_inputs = pd.read_csv(kicker_inputs_path)
        for _, row in kicker_inputs.iterrows():
            result = project_kicker(row)
            rows.append({
                "player_name": row["player_name"],
                "position": "K",
                "nfl_team": to_nickname(row.get("nfl_team", "")),
                "projected_points": result["projected_points"],
                "floor": result["floor"],
                "ceiling": result["ceiling"],
                "risk_tier": result["risk_tier"],
                "explanation": _explain(result),
            })

    out = pd.DataFrame(rows)

    if os.path.exists(bye_weeks_path):
        byes = pd.read_csv(bye_weeks_path)[["team", "bye_week"]]
        out = out.merge(byes, left_on="nfl_team", right_on="team", how="left").drop(columns=["team"])
    else:
        out["bye_week"] = pd.NA

    out = _rescale_to_scored_weeks(out, schedule_path, defense_strength_path)

    # pos_rank/replacement_points stay meaningful (based on the real,
    # unweighted point total); `vor` itself is then overwritten below with
    # a blend of VOR computed separately per phase -- see the note on
    # position_vor() for why that has to happen *after* VOR, not on raw
    # points, to avoid a high-raw-scoring position (QB, in this format)
    # swamping the blend just because of its scale.
    out = compute_vor(out, value_col="projected_points")
    vor_early = position_vor(out, "points_early")
    vor_late = position_vor(out, "points_late")
    out["vor"] = (vor_early + LATE_WEIGHT * vor_late).round(1)
    # Real, lead-role RB scarcity correction -- see apply_bell_cow_scarcity's
    # docstring. Applied last, after the phase blend, since it's a
    # season-long workload signal, not a per-phase one.
    out = apply_bell_cow_scarcity(out)
    out = rank_from_vor(out)
    out = attach_market_adp(out, MARKET_ADP_PATH)
    out = compute_position_tiers(out)
    out = compute_tier_dropoff(out)

    return out.sort_values("overall_rank").reset_index(drop=True)


def attach_market_adp(out: pd.DataFrame, market_adp_path: str) -> pd.DataFrame:
    """Attaches real, sourced consensus ADP (data/research/market_adp_2026.csv)
    as `market_round`/`market_overall_pick`, kept deliberately separate from
    `vor_round`.

    These answer two different real questions and must never be conflated
    (a mistake this board made concretely with Chase Brown and Omarion
    Hampton, Aug 2026 -- both got the internal VOR round printed as if it
    were "the round you can expect to get him," when real market ADP had
    them 1-3 rounds earlier): `vor_round` is our own model's opinion of a
    player's true value relative to replacement, used to decide the best
    pick *among what's actually still on the board*. `market_round` is
    what real consensus (Field Yates/ESPN, other outlets, averaged where
    they disagree) says other real managers will actually do, used to
    predict *whether a player will still be on the board at all*. A
    player can legitimately have very different values here -- that's not
    a bug to reconcile, it's the whole reason VOR-based value-hunting
    works (the gap is where you find steals).

    Source ADP is pick-order data from standard-size drafts (most public
    consensus defaults to a 10-12 team baseline); converted to this
    league's 16-team round via ceil(pick / 16). That's a real, disclosed,
    but approximate adjustment -- overall pick *order* is reasonably
    format-invariant for skill positions, but this hasn't been separately
    re-derived for a 16-team full-IDP league specifically, so treat
    `market_round` as directionally real, not to-the-pick precise.

    Coverage is intentionally partial: bulk ADP sources are blocked from
    automated fetch in this environment, so this file holds only
    individually verified players (skill positions, mostly rounds 1-5) --
    not a full-board audit. Unmatched players get `market_round` = NaN and
    `market_verified` = False; downstream code and the report must treat
    that as "not checked against real consensus," never silently fall back
    to treating vor_round as if it were market_round.
    """
    out = out.copy()
    out["market_verified"] = False
    out["market_round"] = pd.NA
    out["market_overall_pick"] = pd.NA
    if not os.path.exists(market_adp_path):
        return out
    adp = pd.read_csv(market_adp_path)
    adp["market_round"] = (adp["market_overall_pick"] / 16.0).apply(lambda p: int(-(-p // 1)))
    lookup = adp.set_index("player_name")[["market_overall_pick", "market_round"]]
    for name, row in lookup.iterrows():
        mask = out["player_name"] == name
        if mask.any():
            out.loc[mask, "market_overall_pick"] = row["market_overall_pick"]
            out.loc[mask, "market_round"] = row["market_round"]
            out.loc[mask, "market_verified"] = True
    return out


FULL_SEASON_AVAILABLE_WEEKS = 16.0  # a healthy player's real season, net of their own bye

# Weeks 9-12 (the knockout bracket) count extra toward draft value, on top
# of the real per-phase schedule adjustment below -- this is the explicit
# "good enough weeks 4-8, best team weeks 9-12" priority, applied as a
# deliberate tilt on `playoff_weighted_points` (used only for VOR/rank),
# never on `projected_points` (the honest, unweighted real projection).
LATE_WEIGHT = 1.5


def _effective_weeks(bye_week, week_range) -> int:
    weeks = list(week_range)
    return len(weeks) - 1 if bye_week in weeks else len(weeks)


def _rescale_to_scored_weeks(out: pd.DataFrame, schedule_path: str, defense_strength_path: str) -> pd.DataFrame:
    """`projected_points`/floor/ceiling as built above are full-real-season
    totals (17 weeks, net of the player's own bye) -- correct for Top Teamz
    and Electric Blue, which score a normal season, but Rivals only scores
    weeks 4-12 (9 weeks), split into two very different phases: weeks 4-8
    (group stage, floor matters) and weeks 9-12 (single-elimination
    knockout, ceiling matters -- and it's what a roster is actually built
    for). This rescales each player's per-game rate across those two
    phases separately, accounting for:
      - a bye landing inside a phase costing a real game in that phase
        only (a bye at weeks 1-3 or 13+ costs nothing in either phase)
      - each phase's *real* schedule strength (see schedule_strength.py --
        run defense for RBs, pass defense for QB/WR/TE, sourced from real
        2026 preseason team data, neutral where no real signal exists)
    `projected_points`/floor/ceiling stay the honest combined real
    projection; `points_early`/`points_late` (this function's other output)
    feed into a separate per-phase VOR blend in build() that applies
    LATE_WEIGHT to the weeks 9-12 phase specifically, per the explicit
    request to prioritize the knockout weeks while still fully counting
    the group stage.
    """
    out = out.copy()
    schedule = load_schedule(schedule_path)
    defense = load_defense_strength(defense_strength_path)

    per_game_rate = out["projected_points"] / FULL_SEASON_AVAILABLE_WEEKS
    old_points = out["projected_points"].replace(0, 1e-9)

    early_weeks = out["bye_week"].apply(lambda b: _effective_weeks(b, EARLY_WEEKS))
    late_weeks = out["bye_week"].apply(lambda b: _effective_weeks(b, LATE_WEEKS))

    early_mult = out.apply(
        lambda r: week_range_multiplier(r["nfl_team"], r["position"], EARLY_WEEKS, schedule, defense),
        axis=1,
    )
    late_mult = out.apply(
        lambda r: week_range_multiplier(r["nfl_team"], r["position"], LATE_WEEKS, schedule, defense),
        axis=1,
    )

    points_early = per_game_rate * early_weeks * early_mult
    points_late = per_game_rate * late_weeks * late_mult

    real_scale = (points_early + points_late) / old_points
    out["projected_points"] = (points_early + points_late).round(1)
    out["floor"] = (out["floor"] * real_scale).round(1)
    out["ceiling"] = (out["ceiling"] * real_scale).round(1)
    out["points_early"] = points_early.round(1)
    out["points_late"] = points_late.round(1)
    return out


def main():
    out = build()
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    out.to_csv(OUT_PATH, index=False)
    print(f"Wrote {len(out)} players to {OUT_PATH}")


if __name__ == "__main__":
    main()
