"""Turns a model.py result + the input row into the human-readable "why" that
ships with every ranking. This is the whole point of the rebuild: a reader
should be able to see exactly which real inputs produced the number, not just
trust a rank.
"""
from __future__ import annotations

from .team_context import TeamContext


def build_explanation(name: str, position: str, team_name: str, team: TeamContext, row, result: dict) -> str:
    parts = []

    role_tier = _text(row, "role_tier")
    if role_tier:
        parts.append(f"{role_tier} role")

    parts.extend(result["drivers"])
    if team_name in ("Free agent", "Uncertain", ""):
        parts.append("no confirmed 2026 team, so no team-environment adjustment is applied (treated as league-average)")
    else:
        possessive = f"{team_name}'" if team_name.endswith("s") else f"{team_name}'s"
        parts.append(f"plays in {possessive} {team.env_summary()}")

    game_script_note = _text(row, "environment_note")
    if game_script_note:
        parts.append(game_script_note)

    personnel_note = _text(row, "personnel_note")
    if personnel_note:
        parts.append(f"2026 change: {personnel_note}")

    market_note = _text(row, "market_note")
    if market_note:
        parts.append(f"market signal: {market_note}")

    risk_note = _text(row, "risk_note")
    risk_tier = result["risk_tier"]
    if risk_note:
        parts.append(f"risk ({risk_tier}): {risk_note}")
    else:
        parts.append(f"risk tier: {risk_tier}")

    games = result["games_proj"]
    if games < 16.5:
        parts.append(f"projected for {games:.0f} games (injury/role-share discount already applied)")

    body = "; ".join(p for p in parts if p)
    return (
        f"{body}. Median {result['projected_points']:.0f} pts, "
        f"floor {result['floor']:.0f}, ceiling {result['ceiling']:.0f}."
    )


def _text(row, key):
    val = row.get(key)
    if val is None:
        return ""
    try:
        if isinstance(val, float) and val != val:
            return ""
    except TypeError:
        pass
    val = str(val).strip()
    return "" if val.lower() == "nan" else val
