"""Tests the real, lead-role RB scarcity correction (see
value.bell_cow_scarcity_multiplier's docstring for the full reasoning): a
flat VOR replacement curve smooths over a real discontinuity between true
3-down bell-cow backs and the committee/timeshare backs replacement level
is actually measured against, which structurally undervalues the scarce
lead-role tier relative to real ADP (Gibbs/Bijan/McCaffrey going top-5 in
real drafts despite a much lower flat-curve VOR rank here).

Not testing a specific fixed multiplier value (it moves as the real
workload data and flex-share measurement change) -- testing the
*mechanism*: real lead-role supply below real structural demand produces
a real premium, and that premium only touches the lead-role RB tier.
"""
from __future__ import annotations

import pandas as pd

from draft_helper.rivals.value import (
    BELL_COW_RUSH_ATT_THRESHOLD,
    apply_bell_cow_scarcity,
    bell_cow_scarcity_multiplier,
)


def _synthetic_pool(num_bell_cows: int) -> pd.DataFrame:
    rows = []
    for i in range(num_bell_cows):
        rows.append({
            "player_name": f"BellCow{i}", "position": "RB",
            "vor": 100 - i, "rush_att_pg": 16.0,
        })
    for i in range(40):
        rows.append({
            "player_name": f"Committee{i}", "position": "RB",
            "vor": 40 - i, "rush_att_pg": 8.0,
        })
    for i in range(60):
        rows.append({
            "player_name": f"WR{i}", "position": "WR",
            "vor": 90 - i, "rush_att_pg": pd.NA,
        })
    return pd.DataFrame(rows)


def test_multiplier_is_real_premium_when_supply_is_scarce():
    # 16 teams * (1 + 0.50 RB flex share) = 24 real structural demand for
    # lead-role slots; only 10 real bell-cows supplied here -> real, > 1x
    # premium, not an arbitrary round number.
    pool = _synthetic_pool(num_bell_cows=10)
    mult = bell_cow_scarcity_multiplier(pool)
    assert mult == 24 / 10


def test_multiplier_is_flat_when_supply_meets_demand():
    pool = _synthetic_pool(num_bell_cows=30)
    mult = bell_cow_scarcity_multiplier(pool)
    assert mult == 1.0


def test_apply_only_touches_bell_cow_rbs_not_committee_backs_or_other_positions():
    pool = _synthetic_pool(num_bell_cows=10)
    out = apply_bell_cow_scarcity(pool)

    bell_cow = out[out["player_name"] == "BellCow0"].iloc[0]
    committee = out[out["player_name"] == "Committee0"].iloc[0]
    wr = out[out["player_name"] == "WR0"].iloc[0]

    assert bell_cow["vor"] > 100  # boosted above its raw 100
    assert committee["vor"] == 40  # untouched -- below the workload threshold
    assert wr["vor"] == 90  # untouched -- not RB at all


def test_real_2026_data_shows_a_genuine_lead_role_scarcity():
    """Not a synthetic check -- confirms the real, current player pool
    actually has fewer true bell-cows than structural demand, which is
    the real-world condition this whole correction depends on. If this
    ever fails, the correction should stop firing on its own (the
    multiplier already floors at 1.0), but it's worth knowing the real
    data changed enough that the premise no longer holds.
    """
    inputs = pd.read_csv("data/projections/inputs_2026.csv")
    rb = inputs[inputs["position"] == "RB"]
    supply = int((rb["rush_att_pg"] >= BELL_COW_RUSH_ATT_THRESHOLD).sum())
    assert supply < 24, (
        f"real bell-cow supply ({supply}) no longer below structural demand (24) -- "
        "the scarcity correction's real-world premise has changed"
    )
