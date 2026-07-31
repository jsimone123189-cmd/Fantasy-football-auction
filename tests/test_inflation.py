import pandas as pd
import pytest

from draft_helper.analysis.inflation import baseline_value, build_position_rank_curve, inflation_rate


def make_df():
    rows = [
        dict(season="2022", position="RB", cost=100),
        dict(season="2022", position="RB", cost=50),
        dict(season="2022", position="WR", cost=50),
        dict(season="2023", position="RB", cost=80),
        dict(season="2023", position="RB", cost=40),
        dict(season="2023", position="WR", cost=80),
    ]
    return pd.DataFrame(rows)


def test_build_position_rank_curve_shares():
    curve = build_position_rank_curve(make_df())

    rb1 = curve[(curve.position == "RB") & (curve.pos_rank == 1)].iloc[0]
    rb2 = curve[(curve.position == "RB") & (curve.pos_rank == 2)].iloc[0]
    wr1 = curve[(curve.position == "WR") & (curve.pos_rank == 1)].iloc[0]

    assert rb1["avg_cost_share"] == pytest.approx((0.5 + 0.4) / 2)
    assert rb2["avg_cost_share"] == pytest.approx((0.25 + 0.2) / 2)
    assert wr1["avg_cost_share"] == pytest.approx((0.25 + 0.4) / 2)


def test_baseline_value_scales_with_budget():
    curve = build_position_rank_curve(make_df())
    assert baseline_value(curve, "RB", 1, 200) == pytest.approx(90.0)
    assert baseline_value(curve, "RB", 1, 400) == pytest.approx(180.0)


def test_baseline_value_falls_back_to_nearest_rank():
    curve = build_position_rank_curve(make_df())
    # No RB rank-3 data; should fall back to nearest known rank (2).
    rank2 = baseline_value(curve, "RB", 2, 200)
    rank3 = baseline_value(curve, "RB", 3, 200)
    assert rank3 == rank2


def test_baseline_value_unknown_position_floors_at_min_dollar():
    curve = build_position_rank_curve(make_df())
    assert baseline_value(curve, "DEF", 1, 200) == 1.0


def test_inflation_rate_above_one_when_room_is_hot():
    rate = inflation_rate(total_budget=200, dollars_spent=100, baseline_value_drafted=90, baseline_value_total=180)
    assert rate == pytest.approx(100 / 90)


def test_inflation_rate_defaults_to_one_when_no_value_left():
    rate = inflation_rate(total_budget=200, dollars_spent=200, baseline_value_drafted=180, baseline_value_total=180)
    assert rate == 1.0
