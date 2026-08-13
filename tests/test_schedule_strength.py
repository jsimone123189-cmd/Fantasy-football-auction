import pandas as pd
import pytest

from draft_helper.rivals.schedule_strength import week_range_multiplier
from draft_helper.rivals.value import compute_vor, position_vor, rank_from_vor

SCHEDULE = {
    "Alpha": {4: "Beta", 5: "Gamma", 6: "BYE", 7: "Beta", 8: "Gamma"},
    "Beta": {4: "Alpha", 5: "Gamma", 6: "Alpha", 7: "Alpha", 8: "Gamma"},
}
DEFENSE = {
    "Beta": {"run": "tough", "pass": "neutral"},
    "Gamma": {"run": "weak", "pass": "tough"},
}


def test_week_range_multiplier_averages_non_bye_weeks_for_relevant_tier():
    # RB on Alpha, weeks 4-8: opponents are Beta(tough run), Gamma(weak run), BYE, Beta(tough), Gamma(weak).
    mult = week_range_multiplier("Alpha", "RB", range(4, 9), SCHEDULE, DEFENSE)
    assert mult == pytest.approx((0.92 + 1.08 + 0.92 + 1.08) / 4)


def test_week_range_multiplier_uses_pass_tier_for_wr():
    # WR on Alpha faces Gamma (tough pass) twice and Beta (neutral pass) twice, one bye.
    mult = week_range_multiplier("Alpha", "WR", range(4, 9), SCHEDULE, DEFENSE)
    assert mult == pytest.approx((1.0 + 0.92 + 1.0 + 0.92) / 4)


def test_week_range_multiplier_neutral_for_idp_and_kicker():
    assert week_range_multiplier("Alpha", "LB", range(4, 9), SCHEDULE, DEFENSE) == 1.0
    assert week_range_multiplier("Alpha", "K", range(4, 9), SCHEDULE, DEFENSE) == 1.0


def test_week_range_multiplier_defaults_neutral_for_unknown_team():
    assert week_range_multiplier("Unknown Team", "RB", range(4, 9), SCHEDULE, DEFENSE) == 1.0


def test_position_vor_matches_compute_vor_single_phase():
    df = pd.DataFrame([
        {"player_name": f"WR{i}", "position": "WR", "projected_points": 100 - i}
        for i in range(70)
    ])
    via_compute = compute_vor(df, num_teams=16)["vor"]
    via_position_vor = position_vor(df, "projected_points", num_teams=16)
    assert list(via_compute) == list(via_position_vor)


def test_blended_late_weight_favors_player_with_better_late_phase():
    # Two otherwise-identical-total-points players: one scores more in the
    # "late" phase, one more in the "early" phase. Weighting late VOR higher
    # should rank the late-loaded player above the early-loaded one, even
    # though their combined raw totals are equal.
    df = pd.DataFrame([
        {"player_name": "EarlyLoaded", "position": "WR", "points_early": 80, "points_late": 20},
        {"player_name": "LateLoaded", "position": "WR", "points_early": 20, "points_late": 80},
    ] + [
        {"player_name": f"Replacement{i}", "position": "WR", "points_early": 10, "points_late": 10}
        for i in range(70)
    ])
    df["projected_points"] = df["points_early"] + df["points_late"]

    vor_early = position_vor(df, "points_early", num_teams=16)
    vor_late = position_vor(df, "points_late", num_teams=16)
    df["vor"] = (vor_early + 1.35 * vor_late).round(1)
    ranked = rank_from_vor(df, num_teams=16)

    early = ranked[ranked.player_name == "EarlyLoaded"].iloc[0]
    late = ranked[ranked.player_name == "LateLoaded"].iloc[0]
    assert late["overall_rank"] < early["overall_rank"]


def test_blended_vor_does_not_let_high_scale_position_dominate_purely_on_raw_points():
    # QBs score much bigger raw totals than WRs in this format. A modest
    # late-week weight applied on top of *phase-VOR* (not raw points)
    # should not push the entire QB pool above the entire WR pool just
    # because QB point totals are larger in scale.
    qb_rows = [
        {"player_name": f"QB{i}", "position": "QB", "points_early": 100 - i, "points_late": 100 - i}
        for i in range(20)
    ]
    wr_rows = [
        {"player_name": f"WR{i}", "position": "WR", "points_early": 60 - i, "points_late": 60 - i}
        for i in range(70)
    ]
    df = pd.DataFrame(qb_rows + wr_rows)
    df["projected_points"] = df["points_early"] + df["points_late"]

    vor_early = position_vor(df, "points_early", num_teams=16)
    vor_late = position_vor(df, "points_late", num_teams=16)
    df["vor"] = (vor_early + 1.35 * vor_late).round(1)
    ranked = rank_from_vor(df, num_teams=16)

    top_10 = ranked.sort_values("overall_rank").head(10)
    assert (top_10["position"] == "WR").any(), "top of the board should not be pure QB"
