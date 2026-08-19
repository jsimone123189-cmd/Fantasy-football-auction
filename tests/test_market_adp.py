"""Tests attach_market_adp (draft_helper/rivals/build.py): real, sourced
consensus ADP kept as a field separate from our own vor_round -- see that
function's docstring for why the two must never be conflated (this board
concretely got Chase Brown and, on the first attempted fix, Omarion
Hampton wrong by treating vor_round as if it predicted real availability).
"""
from __future__ import annotations

import os
import tempfile

import pandas as pd

from draft_helper.rivals.build import attach_market_adp


def _base_df():
    return pd.DataFrame(
        [
            {"player_name": "Real Player A", "position": "RB", "vor_round": 4},
            {"player_name": "Real Player B", "position": "RB", "vor_round": 6},
        ]
    )


def test_verified_player_gets_real_market_round_and_flag():
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "adp.csv")
        pd.DataFrame(
            [{"player_name": "Real Player A", "position": "RB", "market_overall_pick": 17.6, "source_note": "x"}]
        ).to_csv(path, index=False)
        out = attach_market_adp(_base_df(), path)
    row_a = out[out["player_name"] == "Real Player A"].iloc[0]
    assert row_a["market_verified"] is True or row_a["market_verified"] == True  # noqa: E712
    assert row_a["market_round"] == 2  # ceil(17.6 / 16)
    assert row_a["market_overall_pick"] == 17.6


def test_unverified_player_is_never_silently_backfilled_from_vor_round():
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "adp.csv")
        pd.DataFrame(
            [{"player_name": "Real Player A", "position": "RB", "market_overall_pick": 17.6, "source_note": "x"}]
        ).to_csv(path, index=False)
        out = attach_market_adp(_base_df(), path)
    row_b = out[out["player_name"] == "Real Player B"].iloc[0]
    assert row_b["market_verified"] == False  # noqa: E712
    assert pd.isna(row_b["market_round"])


def test_missing_market_adp_file_leaves_everyone_unverified_not_broken():
    out = attach_market_adp(_base_df(), "/nonexistent/path/adp.csv")
    assert (out["market_verified"] == False).all()  # noqa: E712
    assert out["market_round"].isna().all()


def test_round_boundary_matches_16_team_snake_math():
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "adp.csv")
        pd.DataFrame(
            [
                {"player_name": "Real Player A", "position": "RB", "market_overall_pick": 16.0, "source_note": "x"},
                {"player_name": "Real Player B", "position": "RB", "market_overall_pick": 17.0, "source_note": "x"},
            ]
        ).to_csv(path, index=False)
        out = attach_market_adp(_base_df(), path)
    a = out[out["player_name"] == "Real Player A"].iloc[0]
    b = out[out["player_name"] == "Real Player B"].iloc[0]
    assert a["market_round"] == 1  # last pick of round 1
    assert b["market_round"] == 2  # first pick of round 2
