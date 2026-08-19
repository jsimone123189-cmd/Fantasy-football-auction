"""Tests compute_position_tiers/compute_tier_dropoff (draft_helper/rivals/value.py):
real, position-relative cliff detection -- a flat overall rank can't tell
you whether two adjacent players are a real cliff or a rounding error, and
this project's own live-draft reasoning (Allen/Henry/Dak/Tracy, Aug 2026)
showed exactly why that gap matters for an actual pick decision.
"""
from __future__ import annotations

import pandas as pd

from draft_helper.rivals.value import compute_position_tiers, compute_tier_dropoff


def _df(rows):
    return pd.DataFrame(rows)


def test_a_real_cliff_splits_into_separate_tiers():
    # QB1 way out ahead, then a tight plateau of QB2-QB4 -- a real, obvious cliff.
    df = _df([
        {"player_name": "Elite QB", "position": "QB", "vor": 100.0},
        {"player_name": "Mid QB A", "position": "QB", "vor": 40.0},
        {"player_name": "Mid QB B", "position": "QB", "vor": 39.0},
        {"player_name": "Mid QB C", "position": "QB", "vor": 38.0},
    ])
    out = compute_position_tiers(df)
    tiers = dict(zip(out["player_name"], out["tier"]))
    assert tiers["Elite QB"] == 1
    assert tiers["Mid QB A"] == tiers["Mid QB B"] == tiers["Mid QB C"] == 2


def test_a_smooth_plateau_stays_one_tier():
    # Evenly-spaced small gaps -- no real cliff, should stay one tier.
    df = _df([
        {"player_name": f"WR{i}", "position": "WR", "vor": 50.0 - i} for i in range(6)
    ])
    out = compute_position_tiers(df)
    assert out["tier"].nunique() == 1


def test_tiers_are_computed_independently_per_position():
    df = _df([
        {"player_name": "Elite QB", "position": "QB", "vor": 100.0},
        {"player_name": "Replacement QB", "position": "QB", "vor": 10.0},
        {"player_name": "Elite RB", "position": "RB", "vor": 90.0},
        {"player_name": "Replacement RB", "position": "RB", "vor": 9.0},
    ])
    out = compute_position_tiers(df)
    # each position's own cliff is independent of the other position's scale
    assert out.loc[out["player_name"] == "Elite QB", "tier"].iloc[0] == 1
    assert out.loc[out["player_name"] == "Elite RB", "tier"].iloc[0] == 1
    assert out.loc[out["player_name"] == "Replacement QB", "tier"].iloc[0] == 2
    assert out.loc[out["player_name"] == "Replacement RB", "tier"].iloc[0] == 2


def test_tier_dropoff_is_the_real_points_lost_to_the_next_tier():
    df = _df([
        {"player_name": "Elite QB", "position": "QB", "vor": 100.0, "market_round": 2.0},
        {"player_name": "Mid QB A", "position": "QB", "vor": 40.0, "market_round": 4.0},
        {"player_name": "Mid QB B", "position": "QB", "vor": 39.0, "market_round": 5.0},
    ])
    out = compute_position_tiers(df)
    out = compute_tier_dropoff(out)
    elite = out[out["player_name"] == "Elite QB"].iloc[0]
    assert elite["tier_dropoff"] == 60.0  # 100.0 - 40.0
    # Mid QB A/B are only 1.0 VOR apart -- correctly one tier, not split on noise.
    assert elite["tier_market_rounds"] == "4-5"  # the *next* tier's real ADP span


def test_last_tier_at_a_position_has_zero_dropoff_not_a_crash():
    df = _df([
        {"player_name": "Elite QB", "position": "QB", "vor": 100.0},
        {"player_name": "Mid QB", "position": "QB", "vor": 40.0},
        {"player_name": "Deep QB", "position": "QB", "vor": 1.0},
    ])
    out = compute_position_tiers(df)
    out = compute_tier_dropoff(out)
    deepest_tier = out["tier"].max()
    deepest_rows = out[out["tier"] == deepest_tier]
    assert (deepest_rows["tier_dropoff"] == 0.0).all()
