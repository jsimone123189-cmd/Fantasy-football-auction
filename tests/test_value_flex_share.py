"""Reproduces the empirical measurement behind value.FLEX_SHARE (see that
module's docstring): who actually wins the RWT flex slot in a neutral
16-team best-value-available draft, sampled over many jittered trials to
smooth out the small-sample noise a single 16-team draft has.

This isn't testing a specific fixed constant (FLEX_SHARE can be re-tuned
as the player pool changes) -- it's testing the *finding* that motivated
the correction: RB wins the flex a lot more often than its single
dedicated slot would suggest, because with only 1 dedicated RB slot, a
team's RB2 is frequently still better than its WR4 in this full-PPR
format. A regression back toward "WR dominates the flex" would mean
either the player pool changed a lot or the flex-fill logic broke.
"""
from __future__ import annotations

import random

import pandas as pd

from draft_helper.rivals.build import build
from draft_helper.rivals.mock_draft import FLEX_ELIGIBLE, STARTERS, simulate_draft


def _empirical_flex_share(pool: pd.DataFrame, trials: int, seed: int) -> dict:
    rng = random.Random(seed)
    totals = {"RB": 0, "WR": 0, "TE": 0}

    for _ in range(trials):
        jittered = pool.copy()
        jittered["vor"] = jittered["vor"] + [rng.uniform(-0.5, 0.5) for _ in range(len(jittered))]
        rosters = simulate_draft(jittered, num_teams=16, rounds=18)

        for roster in rosters.values():
            by_pos: dict[str, list[dict]] = {}
            for p in roster:
                by_pos.setdefault(p["position"], []).append(p)
            for pos in by_pos:
                by_pos[pos].sort(key=lambda r: r["projected_points"], reverse=True)

            used_ids = set()
            for pos, n in STARTERS.items():
                for p in by_pos.get(pos, [])[:n]:
                    used_ids.add(id(p))

            remaining = [
                p for pos in FLEX_ELIGIBLE for p in by_pos.get(pos, []) if id(p) not in used_ids
            ]
            remaining.sort(key=lambda r: r["projected_points"], reverse=True)
            if remaining:
                totals[remaining[0]["position"]] += 1

    grand_total = sum(totals.values())
    return {k: v / grand_total for k, v in totals.items()}


def test_rb_wins_flex_more_often_than_its_dedicated_slot_share_alone_would_suggest():
    pool = build()
    share = _empirical_flex_share(pool, trials=40, seed=7)

    # RB has 1 of 5 dedicated RWT-relevant slots (1 RB + 3 WR + 1 TE = 5),
    # i.e. 20% by slot count alone -- but wins the flex far more than that.
    assert share["RB"] > 0.35, f"expected RB to win flex well above its 20% slot-count share, got {share}"
    # WR, despite 3 dedicated slots, should not dominate the flex the way
    # a naive "more slots = more flex demand" assumption would predict.
    assert share["WR"] < share["RB"], f"expected RB to win more flex slots than WR, got {share}"
