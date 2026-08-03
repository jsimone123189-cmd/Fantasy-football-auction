"""Builds data/projections/2026.csv from the raw per-player input drivers.

Run as: python -m draft_helper.projections.build

Reads:
  - data/projections/inputs_2026.csv   (per-player opportunity/efficiency/
    risk drivers -- the actual "explainable data" the model runs on)
  - data/research/team_context_2026.csv (Vegas lines, O-line, scheme, coaching
    -- see team_context.py for how this becomes multipliers)
  - data/projections/def_2026.csv       (DEF/ST projections; see that file's
    own header -- kept separate because DEF units aren't projected from the
    same opportunity/efficiency framework as skill players)

Writes:
  - data/projections/2026.csv with columns player_name, position, nfl_team,
    projected_points, floor, ceiling, projected_rank, risk_tier, explanation
    -- projected_rank is this player's rank *within their position* by
    median points, which is what feeds draft_helper's existing $ pricing
    pipeline (it prices players by position + rank against your league's
    real historical curve, unchanged from before this rebuild).
"""
from __future__ import annotations

import os

import pandas as pd

from .model import PROJECTORS
from .explain import build_explanation
from .team_context import DEFAULT_IMPLIED_PPG, TeamContext, load_team_contexts

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
INPUTS_PATH = os.path.join(BASE_DIR, "data", "projections", "inputs_2026.csv")
DEF_PATH = os.path.join(BASE_DIR, "data", "projections", "def_2026.csv")
TEAM_CONTEXT_PATH = os.path.join(BASE_DIR, "data", "research", "team_context_2026.csv")
OUT_PATH = os.path.join(BASE_DIR, "data", "projections", "2026.csv")


def build(inputs_path=INPUTS_PATH, team_context_path=TEAM_CONTEXT_PATH, def_path=DEF_PATH) -> pd.DataFrame:
    inputs = pd.read_csv(inputs_path)
    contexts = load_team_contexts(team_context_path)
    league_avg_ppg = (
        pd.Series([c.implied_ppg for c in contexts.values()]).mean()
        if contexts else DEFAULT_IMPLIED_PPG
    )

    rows = []
    for _, row in inputs.iterrows():
        position = str(row["position"]).strip().upper()
        team_name = str(row.get("nfl_team", "")).strip()
        team_ctx = contexts.get(team_name) or TeamContext(None, league_avg_ppg)

        projector = PROJECTORS.get(position)
        if projector is None:
            continue
        result = projector(row, team_ctx)
        explanation = build_explanation(row["player_name"], position, team_name, team_ctx, row, result)

        rows.append({
            "player_name": row["player_name"],
            "position": position,
            "nfl_team": team_name,
            "projected_points": result["projected_points"],
            "floor": result["floor"],
            "ceiling": result["ceiling"],
            "risk_tier": result["risk_tier"],
            "explanation": explanation,
        })

    out = pd.DataFrame(rows)

    if os.path.exists(def_path):
        def_df = pd.read_csv(def_path)
        def_df = def_df.rename(columns={"team": "player_name"})
        def_df["position"] = "DEF"
        if "nfl_team" not in def_df.columns:
            def_df["nfl_team"] = def_df["player_name"]
        out = pd.concat([out, def_df[out.columns]], ignore_index=True)

    out["projected_rank"] = out.groupby("position")["projected_points"].rank(ascending=False, method="first").astype(int)
    out = out.sort_values(["position", "projected_rank"]).reset_index(drop=True)
    return out


def main():
    out = build()
    out.to_csv(OUT_PATH, index=False)
    print(f"Wrote {len(out)} players to {OUT_PATH}")


if __name__ == "__main__":
    main()
