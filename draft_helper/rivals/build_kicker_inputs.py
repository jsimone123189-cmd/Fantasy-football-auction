"""Turns real 2025 kicker season totals (`data/research/kickers_2026.csv`)
into per-game rate inputs for `model.project_kicker`
(`data/rivals/inputs_kicker_2026.csv`). fg_missed/xp_missed are derived as
attempts minus makes, not separately researched -- that's exact arithmetic,
not an estimate.

Run as: python -m draft_helper.rivals.build_kicker_inputs
"""
from __future__ import annotations

import os

import pandas as pd

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SOURCE_PATH = os.path.join(BASE_DIR, "data", "research", "kickers_2026.csv")
OUT_PATH = os.path.join(BASE_DIR, "data", "rivals", "inputs_kicker_2026.csv")

RISK_BASE_GAMES = {"locked-in starter": 17, "open competition": 13, "unsigned": 10}


def _rate(total, games):
    total = pd.to_numeric(total, errors="coerce")
    if pd.isna(total) or not games:
        return 0.0
    return float(total) / float(games)


def _risk_tier(role: str) -> str:
    role = (role or "").lower()
    if "unsigned" in role:
        return "high"
    if "competition" in role or "uncertain" in role:
        return "medium"
    return "low"


def build() -> pd.DataFrame:
    if not os.path.exists(SOURCE_PATH):
        return pd.DataFrame()
    df = pd.read_csv(SOURCE_PATH)
    rows = []
    for _, row in df.iterrows():
        role = str(row.get("role_2026", "") or "")
        games_2025 = row.get("games_played_2025", 0) or 0
        role_lower = role.lower()
        games_proj = (
            RISK_BASE_GAMES["unsigned"] if "unsigned" in role_lower else
            RISK_BASE_GAMES["open competition"] if "competition" in role_lower or "uncertain" in role_lower else
            RISK_BASE_GAMES["locked-in starter"]
        )
        games = games_2025 if games_2025 and float(games_2025) > 0 else games_proj

        def _n(key):
            v = pd.to_numeric(row.get(key, 0), errors="coerce")
            return 0.0 if pd.isna(v) else float(v)

        fg_made = _n("fg_made_2025")
        fg_att = _n("fg_att_2025")
        xp_made = _n("xp_made_2025")
        xp_att = _n("xp_att_2025")
        fg_40_49 = _n("fg_40_49_made_2025")
        fg_50plus = _n("fg_50plus_made_2025")

        rows.append({
            "player_name": row["player_name"],
            "nfl_team": str(row.get("nfl_team", "")),
            "games_proj": games_proj,
            "fg_made_pg": round(_rate(fg_made, games), 3),
            "fg_40_49_pg": round(_rate(fg_40_49, games), 3),
            "fg_50plus_pg": round(_rate(fg_50plus, games), 3),
            "xp_made_pg": round(_rate(xp_made, games), 3),
            "fg_missed_pg": round(_rate(max(float(fg_att) - float(fg_made), 0), games), 3),
            "xp_missed_pg": round(_rate(max(float(xp_att) - float(xp_made), 0), games), 3),
            "risk_tier": _risk_tier(role),
            "role_note": role,
        })
    return pd.DataFrame(rows)


def main():
    out = build()
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    out.to_csv(OUT_PATH, index=False)
    print(f"Wrote {len(out)} kickers to {OUT_PATH}")


if __name__ == "__main__":
    main()
