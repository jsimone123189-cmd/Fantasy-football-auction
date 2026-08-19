"""Tests effective_late_weight (draft_helper/rivals/build.py): the
playoff-weeks tilt (LATE_WEIGHT) should apply in full to a real,
plausible active starter/flex, and taper toward neutral for deep bench
-- see that function's docstring for the real reasoning (a user catch
during a live mock: late-round IDP/bench rankings looked wrong because
this tilt was being applied somewhere it doesn't belong).
"""
from __future__ import annotations

import pandas as pd

from draft_helper.rivals.build import LATE_WEIGHT, LATE_WEIGHT_TAPER_ROUNDS, effective_late_weight


def _df(pos_ranks, position="LB"):
    return pd.DataFrame({"position": [position] * len(pos_ranks), "pos_rank": pos_ranks})


def test_a_real_starter_gets_full_late_weight():
    # LB replacement rank is 16 teams x 1 starter = 16 (no flex share).
    out = _df([1, 8, 16])
    w = effective_late_weight(out, num_teams=16)
    assert (w == LATE_WEIGHT).all()


def test_bench_within_the_grace_window_still_gets_full_weight():
    # Real bench depth just past the starter line is still a plausible
    # bye-week/injury replacement, not pure handcuff speculation.
    grace = LATE_WEIGHT_TAPER_ROUNDS * 16
    out = _df([16 + grace])
    w = effective_late_weight(out, num_teams=16)
    assert w.iloc[0] == LATE_WEIGHT


def test_deep_bench_tapers_to_fully_neutral():
    grace = LATE_WEIGHT_TAPER_ROUNDS * 16
    taper_span = grace
    out = _df([16 + grace + taper_span])
    w = effective_late_weight(out, num_teams=16)
    assert w.iloc[0] == 1.0


def test_taper_is_monotonic_between_the_two_endpoints():
    grace = LATE_WEIGHT_TAPER_ROUNDS * 16
    taper_span = grace
    ranks = [16 + grace, 16 + grace + taper_span // 2, 16 + grace + taper_span]
    out = _df(ranks)
    w = effective_late_weight(out, num_teams=16).tolist()
    assert w[0] > w[1] > w[2]
    assert w[0] == LATE_WEIGHT
    assert w[2] == 1.0


def test_flex_eligible_positions_get_a_real_wider_full_weight_zone():
    # RB has real flex demand on top of its 1 dedicated starter, so its
    # replacement rank -- and therefore the full-weight zone -- is
    # correctly wider than a no-flex position like LB.
    from draft_helper.rivals.value import replacement_ranks

    ranks = replacement_ranks(num_teams=16)
    assert ranks["RB"] > ranks["LB"]
