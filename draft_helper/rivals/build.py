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

Writes:
  - data/rivals/2026.csv with columns player_name, position, nfl_team,
    projected_points, floor, ceiling, risk_tier, pos_rank, vor,
    overall_rank, vor_round, explanation, bye_week
"""
from __future__ import annotations

import os

import pandas as pd

from draft_helper.projections.team_context import DEFAULT_IMPLIED_PPG, TeamContext, load_team_contexts

from .model import SKILL_PROJECTORS, project_idp, project_kicker
from .teams import idp_bucket, to_nickname
from .value import compute_vor

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SKILL_INPUTS_PATH = os.path.join(BASE_DIR, "data", "projections", "inputs_2026.csv")
TEAM_CONTEXT_PATH = os.path.join(BASE_DIR, "data", "research", "team_context_2026.csv")
IDP_INPUTS_PATH = os.path.join(BASE_DIR, "data", "rivals", "inputs_idp_2026.csv")
KICKER_INPUTS_PATH = os.path.join(BASE_DIR, "data", "rivals", "inputs_kicker_2026.csv")
BYE_WEEKS_PATH = os.path.join(BASE_DIR, "data", "research", "bye_weeks_2026.csv")
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

    out = _rescale_to_scored_weeks(out)
    out = compute_vor(out)

    return out.sort_values("overall_rank").reset_index(drop=True)


SCORED_WEEKS = set(range(4, 13))  # Rivals only scores weeks 4-12
FULL_SEASON_AVAILABLE_WEEKS = 16.0  # a healthy player's real season, net of their own bye


def _rescale_to_scored_weeks(out: pd.DataFrame) -> pd.DataFrame:
    """`projected_points`/floor/ceiling as built above are full-real-season
    totals (17 weeks, net of the player's own bye) -- correct for Top Teamz
    and Electric Blue, which score a normal season, but Rivals only scores
    weeks 4-12 (9 weeks). A bye landing inside that window (weeks 4-12)
    costs a real scored week; a bye at weeks 1-3 or 13+ costs nothing, since
    those weeks were never going to count anyway. Rescale here so VOR (and
    every downstream draft recommendation) reflects what this league
    actually scores, not a generic full season.
    """
    out = out.copy()
    effective_scored_weeks = out["bye_week"].apply(
        lambda b: (len(SCORED_WEEKS) - 1) if b in SCORED_WEEKS else len(SCORED_WEEKS)
    )
    scale = effective_scored_weeks / FULL_SEASON_AVAILABLE_WEEKS
    for col in ("projected_points", "floor", "ceiling"):
        out[col] = (out[col] * scale).round(1)
    return out


def main():
    out = build()
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    out.to_csv(OUT_PATH, index=False)
    print(f"Wrote {len(out)} players to {OUT_PATH}")


if __name__ == "__main__":
    main()
