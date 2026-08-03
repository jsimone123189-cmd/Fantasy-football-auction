import pandas as pd
import pytest

from draft_helper.projections.scoring import expected_milestone_bonus, score_stat_line
from draft_helper.projections.team_context import TeamContext
from draft_helper.projections.model import project_rb, project_wr_te, project_qb
from draft_helper.projections.def_model import project_defense


def test_score_stat_line_half_ppr():
    # 100 rush yards, 1 rush TD, 5 receptions, 50 rec yards -> confirmed league rules.
    pts = score_stat_line(dict(rush_yards=100, rush_td=1, receptions=5, rec_yards=50))
    assert pts == pytest.approx(100 * 0.1 + 6 + 5 * 0.5 + 50 * 0.1)


def test_score_stat_line_passing_td_is_four_points():
    # Confirmed real league rate: 1 pt / 50 passing yards (not the more common 1/25).
    pts = score_stat_line(dict(pass_yards=300, pass_td=2, interceptions=1))
    assert pts == pytest.approx(300 * 0.02 + 2 * 4 - 2)


def test_expected_milestone_bonus_zero_when_far_below_threshold():
    # A 150 yd/g passer essentially never hits 300 -- bonus should be ~0.
    bonus = expected_milestone_bonus(games=17, pass_yards_per_game=150)
    assert bonus == pytest.approx(0, abs=0.5)


def test_expected_milestone_bonus_grows_with_average_yardage():
    low = expected_milestone_bonus(games=17, pass_yards_per_game=230)
    high = expected_milestone_bonus(games=17, pass_yards_per_game=320)
    assert 0 <= low < high


def test_expected_milestone_bonus_stacks_rush_and_pass():
    combined = expected_milestone_bonus(games=17, pass_yards_per_game=280, rush_yards_per_game=90)
    pass_only = expected_milestone_bonus(games=17, pass_yards_per_game=280)
    rush_only = expected_milestone_bonus(games=17, rush_yards_per_game=90)
    assert combined == pytest.approx(pass_only + rush_only)


def neutral_context(implied_ppg=21.5):
    return TeamContext(None, league_avg_implied_ppg=implied_ppg)


def test_neutral_team_context_multipliers_are_one():
    ctx = neutral_context()
    assert ctx.scoring_mult == pytest.approx(1.0)
    assert ctx.run_funnel_mult == pytest.approx(1.0)
    assert ctx.pass_funnel_mult == pytest.approx(1.0)
    assert ctx.rb_gamescript_mult == pytest.approx(1.0)


def test_good_offense_team_context_boosts_scoring():
    row = pd.Series({
        "implied_ppg": 27.0, "ol_tier": "elite", "scheme_tendency": "run-funnel",
        "pace_tier": "fast", "win_total": 11.5,
    })
    ctx = TeamContext(row, league_avg_implied_ppg=21.5)
    assert ctx.scoring_mult > 1.15
    assert ctx.run_funnel_mult > 1.0
    assert ctx.rb_gamescript_mult > 1.0  # good team -> positive game script -> more RB volume


def test_project_rb_scales_with_volume_and_efficiency():
    ctx = neutral_context()
    lead_back = pd.Series({
        "position": "RB", "games_proj": 17, "rush_att_pg": 18, "ypc": 4.5, "rush_td_rate": 0.04,
        "targets_pg": 3, "catch_rate": 0.8, "ypt": 7, "rec_td_rate": 0.02, "risk_tier": "low",
    })
    backup = pd.Series({
        "position": "RB", "games_proj": 17, "rush_att_pg": 4, "ypc": 4.0, "rush_td_rate": 0.02,
        "targets_pg": 1, "catch_rate": 0.7, "ypt": 6, "rec_td_rate": 0.01, "risk_tier": "high",
    })
    lead_result = project_rb(lead_back, ctx)
    backup_result = project_rb(backup, ctx)
    assert lead_result["projected_points"] > backup_result["projected_points"]
    # Floor/ceiling widen for the riskier backup.
    lead_spread = lead_result["ceiling"] - lead_result["floor"]
    backup_spread_pct = (backup_result["ceiling"] - backup_result["floor"]) / backup_result["projected_points"]
    lead_spread_pct = lead_spread / lead_result["projected_points"]
    assert backup_spread_pct > lead_spread_pct


def test_project_rb_game_script_boosts_volume_for_good_teams():
    row = pd.Series({
        "position": "RB", "games_proj": 17, "rush_att_pg": 15, "ypc": 4.3, "rush_td_rate": 0.03,
        "targets_pg": 2, "catch_rate": 0.75, "ypt": 6, "rec_td_rate": 0.01, "risk_tier": "medium",
    })
    good_team = TeamContext(pd.Series({"win_total": 11.5, "implied_ppg": 24}), 21.5)
    bad_team = TeamContext(pd.Series({"win_total": 5.5, "implied_ppg": 19}), 21.5)
    good_result = project_rb(row, good_team)
    bad_result = project_rb(row, bad_team)
    assert good_result["rush_yards"] > bad_result["rush_yards"]


def test_project_wr_te_uses_targets_and_efficiency():
    ctx = neutral_context()
    wr1 = pd.Series({
        "position": "WR", "games_proj": 17, "targets_pg": 9, "catch_rate": 0.68, "ypt": 8.5,
        "td_rate_per_target": 0.06, "risk_tier": "low",
    })
    result = project_wr_te(wr1, ctx)
    assert result["projected_points"] > 0
    assert result["receptions"] == pytest.approx(9 * 17 * 0.68, rel=0.01)


def test_project_qb_includes_rushing_equity():
    ctx = neutral_context()
    mobile_qb = pd.Series({
        "position": "QB", "games_proj": 17, "pass_att_pg": 33, "comp_pct": 0.65, "pass_ypa": 7.2,
        "pass_td_rate": 0.045, "int_rate": 0.02, "qb_rush_att_pg": 7, "qb_rush_ypc": 5.5,
        "qb_rush_td_rate": 0.06, "risk_tier": "medium",
    })
    pocket_qb = pd.Series({
        "position": "QB", "games_proj": 17, "pass_att_pg": 35, "comp_pct": 0.68, "pass_ypa": 7.4,
        "pass_td_rate": 0.05, "int_rate": 0.02, "qb_rush_att_pg": 1, "qb_rush_ypc": 3.0,
        "qb_rush_td_rate": 0.02, "risk_tier": "low",
    })
    mobile_result = project_qb(mobile_qb, ctx)
    pocket_result = project_qb(pocket_qb, ctx)
    # Rushing equity should meaningfully close the gap despite fewer/less efficient pass attempts.
    assert mobile_result["rush_yards"] > pocket_result["rush_yards"]
    assert mobile_result["projected_points"] > 0


def test_project_defense_scales_with_win_total():
    elite = project_defense("Rams", 11.5)
    poor = project_defense("Cardinals", 3.5)
    assert elite["projected_points"] > poor["projected_points"]
    assert elite["floor"] < elite["projected_points"] < elite["ceiling"]


def test_project_defense_applies_real_signal_bonus():
    with_bonus = project_defense("Rams", 9.5)
    without_bonus = project_defense("SomeOtherTeam", 9.5)
    assert with_bonus["projected_points"] > without_bonus["projected_points"]
