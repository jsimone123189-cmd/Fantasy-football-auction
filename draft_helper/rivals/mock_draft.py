"""Best-player-available (BPA) snake draft simulator, used only to answer
one question: given this roster construction and this year's real VOR
board, which of the 16 draft slots comes out ahead purely from snake-order
mechanics (value cliffs + who gets the "wheel" picks at each turn)?

This is deliberately a *neutral* simulation -- all 16 teams run the exact
same BPA-by-VOR strategy, subject only to Fantrax's real roster position
caps (`ROSTER_MAX`). It does not model the specific tendencies of the 16
named managers in this league (nobody has real history to draw that from
yet -- see the Rivals FCL project memory: "inaugural season, no league
history"). What it *does* isolate is the structural slot advantage: which
picks land right before/after a position's value cliff, and which slots
get two picks close together at the turn.

Run as: python -m draft_helper.rivals.mock_draft
"""
from __future__ import annotations

import os

import pandas as pd

from .value import FLEX_SHARE, NUM_TEAMS, STARTERS

ROSTER_MAX = {"QB": 3, "RB": 4, "WR": 5, "TE": 3, "DL": 3, "LB": 3, "DB": 3, "K": 2}
ROUNDS = 18
FLEX_ELIGIBLE = {"RB", "WR", "TE"}

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PROJECTIONS_PATH = os.path.join(BASE_DIR, "data", "rivals", "2026.csv")


def _snake_order(num_teams: int, rounds: int) -> list[int]:
    order = []
    for rnd in range(rounds):
        seq = list(range(num_teams)) if rnd % 2 == 0 else list(range(num_teams - 1, -1, -1))
        order.extend(seq)
    return order


def simulate_draft(pool: pd.DataFrame, num_teams: int = NUM_TEAMS, rounds: int = ROUNDS) -> dict[int, list[dict]]:
    """Returns {slot_index (0-based): [drafted player rows in pick order]}."""
    available = pool.sort_values("vor", ascending=False).to_dict("records")
    rosters = {i: [] for i in range(num_teams)}
    pos_counts = {i: {} for i in range(num_teams)}

    for slot in _snake_order(num_teams, rounds):
        counts = pos_counts[slot]
        pick = None
        for idx, player in enumerate(available):
            pos = player["position"]
            cap = ROSTER_MAX.get(pos)
            if cap is not None and counts.get(pos, 0) >= cap:
                continue
            pick = available.pop(idx)
            break
        if pick is None:
            continue
        rosters[slot].append(pick)
        counts[pick["position"]] = counts.get(pick["position"], 0) + 1

    return rosters


def optimal_lineup_points(roster: list[dict]) -> float:
    """Greedy best starting lineup under STARTERS + one RWT flex -- fill
    each dedicated slot with the best player at that position, then fill
    FLEX with the best remaining RB/WR/TE.
    """
    by_pos: dict[str, list[dict]] = {}
    for p in roster:
        by_pos.setdefault(p["position"], []).append(p)
    for pos in by_pos:
        by_pos[pos].sort(key=lambda r: r["projected_points"], reverse=True)

    total = 0.0
    used_ids = set()
    for pos, n in STARTERS.items():
        players = by_pos.get(pos, [])
        for p in players[:n]:
            total += p["projected_points"]
            used_ids.add(id(p))

    flex_candidates = [
        p for pos in FLEX_ELIGIBLE for p in by_pos.get(pos, []) if id(p) not in used_ids
    ]
    flex_candidates.sort(key=lambda r: r["projected_points"], reverse=True)
    if flex_candidates:
        total += flex_candidates[0]["projected_points"]

    return round(total, 1)


def rank_draft_slots(pool: pd.DataFrame, num_teams: int = NUM_TEAMS, rounds: int = ROUNDS) -> pd.DataFrame:
    rosters = simulate_draft(pool, num_teams, rounds)
    rows = []
    for slot, roster in rosters.items():
        rows.append({
            "draft_slot": slot + 1,
            "optimal_lineup_points": optimal_lineup_points(roster),
            "roster_size": len(roster),
        })
    out = pd.DataFrame(rows).sort_values("optimal_lineup_points", ascending=False).reset_index(drop=True)
    out["slot_rank"] = out.index + 1
    return out


def main():
    pool = pd.read_csv(PROJECTIONS_PATH)
    ranked = rank_draft_slots(pool)
    with pd.option_context("display.max_rows", None, "display.width", 120):
        print(ranked.to_string(index=False))


if __name__ == "__main__":
    main()
