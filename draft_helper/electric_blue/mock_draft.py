"""Best-player-available (BPA) snake draft simulator for Electric Blue --
same purpose and neutral-sim philosophy as Rivals FCL's mock_draft.py
(see that module's docstring), adapted for Electric Blue's roster shape
and its real 2026 keepers.

Run as: python -m draft_helper.electric_blue.mock_draft
"""
from __future__ import annotations

import os

import pandas as pd

from .value import NUM_TEAMS, STARTERS

ROSTER_MAX = {"QB": 2, "RB": 6, "WR": 6, "TE": 2, "DEF": 1}
ROUNDS = 14
FLEX_ELIGIBLE = {"RB", "WR", "TE"}

# Real multi-season market behavior in this exact league (see tendencies.py /
# def_and_kicker_draft_rounds, which covers past seasons that did have a K
# slot): DEF has never been drafted before round 8, averaging round ~13.
# Pure VOR ranks a top DEF as high as round 3-4 on paper because of this
# league's points-allowed-only DEF scoring -- a real gap over replacement
# level, but one the real market has never actually paid for. Modeling
# every team as pure-VOR BPA would draft DEF in round 6, which contradicts
# this league's own documented history; deferred here for all teams to
# match reality. No kicker this season -- confirmed live during the 2026
# draft that this league dropped the K slot entirely.
DEFER_POSITIONS = {"DEF"}
DEFER_UNTIL_ROUND = ROUNDS - 1

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PROJECTIONS_PATH = os.path.join(BASE_DIR, "data", "electric_blue", "2026.csv")


def _snake_order(num_teams: int, rounds: int) -> list[int]:
    """0-indexed team slot per pick, in real draft-clock order."""
    order = []
    for rnd in range(rounds):
        seq = list(range(num_teams)) if rnd % 2 == 0 else list(range(num_teams - 1, -1, -1))
        order.extend(seq)
    return order


def simulate_draft(
    pool: pd.DataFrame,
    num_teams: int = NUM_TEAMS,
    rounds: int = ROUNDS,
    keepers: dict | None = None,
) -> dict[int, list[dict]]:
    """Returns {slot_index (0-based): [drafted player rows in pick order]}.

    `keepers`: optional {slot_index: [(round, player_name), ...]} -- that
    team's real 2026 keeper(s), pre-removed from the live pool and
    "picked" automatically at their real keeper round instead of a live
    BPA selection. Every other team still picks normally that round.
    """
    keepers = keepers or {}
    kept_names = {name for picks in keepers.values() for _, name in picks}
    available = pool[~pool["player_name"].isin(kept_names)].sort_values("vor", ascending=False).to_dict("records")
    keeper_lookup = {row["player_name"]: row for _, row in pool.iterrows() if row["player_name"] in kept_names}

    rosters = {i: [] for i in range(num_teams)}
    pos_counts = {i: {} for i in range(num_teams)}
    keeper_rounds = {slot: {rnd: name for rnd, name in picks} for slot, picks in keepers.items()}

    current_round = 1
    picks_this_round = 0
    for slot in _snake_order(num_teams, rounds):
        picks_this_round += 1
        if picks_this_round > num_teams:
            current_round += 1
            picks_this_round = 1

        counts = pos_counts[slot]
        kept_name = keeper_rounds.get(slot, {}).get(current_round)
        if kept_name is not None:
            row = keeper_lookup[kept_name]
            rosters[slot].append(dict(row))
            counts[row["position"]] = counts.get(row["position"], 0) + 1
            continue

        pick = None
        for idx, player in enumerate(available):
            pos = player["position"]
            cap = ROSTER_MAX.get(pos)
            if cap is not None and counts.get(pos, 0) >= cap:
                continue
            if pos in DEFER_POSITIONS and current_round < DEFER_UNTIL_ROUND:
                continue
            pick = available.pop(idx)
            break
        if pick is None:
            continue
        rosters[slot].append(pick)
        counts[pick["position"]] = counts.get(pick["position"], 0) + 1

    return rosters


def optimal_lineup_points(roster: list[dict]) -> float:
    """Greedy best starting lineup: fill each dedicated slot with the best
    player at that position, then fill the single W/R/T flex with the best
    remaining RB/WR/TE.
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


def main():
    pool = pd.read_csv(PROJECTIONS_PATH)
    rosters = simulate_draft(pool)
    for slot, roster in rosters.items():
        pts = optimal_lineup_points(roster)
        print(f"Slot {slot + 1}: {pts} optimal starting points")


if __name__ == "__main__":
    main()
