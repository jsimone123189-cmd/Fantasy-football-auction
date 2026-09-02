"""Builds data/electric_blue/2026.csv -- the full Electric Blue projection
set (QB/RB/WR/TE/DEF) with VOR-based snake-draft ranking.

No kicker here -- confirmed live during the 2026 draft that this league
has no K slot this season (past seasons did; see tendencies.py's real
historical K/DEF market-timing analysis, which is unaffected by this).

Reuses real inputs already gathered for the other two leagues: skill-
position opportunity/efficiency (Top Teamz) and team context/DEF tiers
(Top Teamz) -- only the scoring formula and roster shape are Electric
Blue's own.

Run as: python -m draft_helper.electric_blue.build
"""
from __future__ import annotations

import os

import pandas as pd

from draft_helper.projections.team_context import DEFAULT_IMPLIED_PPG, TeamContext, load_team_contexts

from .model import SKILL_PROJECTORS, project_defense
from .value import compute_vor

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SKILL_INPUTS_PATH = os.path.join(BASE_DIR, "data", "projections", "inputs_2026.csv")
TEAM_CONTEXT_PATH = os.path.join(BASE_DIR, "data", "research", "team_context_2026.csv")
BYE_WEEKS_PATH = os.path.join(BASE_DIR, "data", "research", "bye_weeks_2026.csv")
OUT_PATH = os.path.join(BASE_DIR, "data", "electric_blue", "2026.csv")


def _explain(result: dict) -> str:
    return " | ".join(result.get("drivers", []))


def build() -> pd.DataFrame:
    rows = []

    contexts = load_team_contexts(TEAM_CONTEXT_PATH) if os.path.exists(TEAM_CONTEXT_PATH) else {}
    league_avg_ppg = (
        pd.Series([c.implied_ppg for c in contexts.values()]).mean() if contexts else DEFAULT_IMPLIED_PPG
    )

    if os.path.exists(SKILL_INPUTS_PATH):
        skill_inputs = pd.read_csv(SKILL_INPUTS_PATH)
        for _, row in skill_inputs.iterrows():
            position = str(row["position"]).strip().upper()
            projector = SKILL_PROJECTORS.get(position)
            if projector is None:
                continue
            team_name = str(row.get("nfl_team", "")).strip()
            team_ctx = contexts.get(team_name) or TeamContext(None, league_avg_ppg)
            result = projector(row, team_ctx)
            rows.append({
                "player_name": row["player_name"], "position": position, "nfl_team": team_name,
                "projected_points": result["projected_points"], "floor": result["floor"],
                "ceiling": result["ceiling"], "risk_tier": result["risk_tier"], "explanation": _explain(result),
            })

    for team_name, ctx in contexts.items():
        result = project_defense(team_name, ctx.win_total if ctx.win_total is not None else 8.5)
        rows.append({
            "player_name": team_name, "position": "DEF", "nfl_team": team_name,
            "projected_points": result["projected_points"], "floor": result["floor"],
            "ceiling": result["ceiling"], "risk_tier": result["risk_tier"], "explanation": _explain(result),
        })

    out = pd.DataFrame(rows)
    out = compute_vor(out)

    if os.path.exists(BYE_WEEKS_PATH):
        byes = pd.read_csv(BYE_WEEKS_PATH)[["team", "bye_week"]]
        out = out.merge(byes, left_on="nfl_team", right_on="team", how="left").drop(columns=["team"])
    else:
        out["bye_week"] = pd.NA

    return out.sort_values("overall_rank").reset_index(drop=True)


def main():
    out = build()
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    out.to_csv(OUT_PATH, index=False)
    print(f"Wrote {len(out)} players to {OUT_PATH}")


if __name__ == "__main__":
    main()
