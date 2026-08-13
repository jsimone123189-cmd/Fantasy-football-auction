import pandas as pd
import pytest

from draft_helper.rivals.scoring import score_idp, score_kicker, score_offense
from draft_helper.rivals.teams import idp_bucket, to_nickname
from draft_helper.rivals.value import compute_vor, replacement_ranks
from draft_helper.rivals.model import project_idp, project_kicker
from draft_helper.rivals.mock_draft import optimal_lineup_points, simulate_draft


def test_score_offense_full_ppr():
    # Full PPR (1.0/reception) and 1pt/25 pass yards -- both different from Top Teamz.
    pts = score_offense(dict(receptions=5, rec_yards=50, rush_yards=100, rush_td=1))
    assert pts == pytest.approx(5 * 1.0 + 50 * 0.1 + 100 * 0.1 + 6)


def test_score_offense_pass_yard_rate_is_double_top_teamz():
    pts = score_offense(dict(pass_yards=300, pass_td=2, interceptions=1))
    assert pts == pytest.approx(300 * 0.04 + 2 * 4 - 2)


def test_score_idp_tackle_heavy():
    # 5 solo, 3 assisted, 1 sack, 1 FF -- confirmed Rivals FCL IDP scoring.
    pts = score_idp(dict(solo_tackles=5, ast_tackles=3, sacks=1, forced_fumbles=1))
    assert pts == pytest.approx(5 * 1.5 + 3 * 0.75 + 4 + 4)


def test_score_kicker_distance_bonuses_stack_on_flat_make():
    # A 52-yard FG made is worth the flat point plus the 50+ bonus (3 total).
    pts = score_kicker(dict(fg_made=1, fg_made_50plus=1))
    assert pts == pytest.approx(1 + 2)


def test_idp_bucket_collapses_sub_positions():
    assert idp_bucket("ILB") == "LB"
    assert idp_bucket("OLB") == "LB"
    assert idp_bucket("WLB") == "LB"
    assert idp_bucket("DE") == "DL"
    assert idp_bucket("NT") == "DL"
    assert idp_bucket("CB") == "DB"
    assert idp_bucket("FS") == "DB"


def test_to_nickname_normalizes_abbreviations():
    assert to_nickname("SF") == "49ers"
    assert to_nickname("WAS") == "Commanders"
    assert to_nickname("Bengals") == "Bengals"  # already a nickname -> passthrough


def test_project_idp_scores_tackle_volume():
    row = pd.Series(dict(
        player_name="Test LB", position="LB", nfl_team="Lions", games_proj=17,
        solo_pg=5.0, ast_pg=3.0, tfl_pg=0.3, sack_pg=0.1, ff_pg=0.05, fr_pg=0.02,
        int_pg=0.05, pd_pg=0.2, risk_tier="low",
    ))
    result = project_idp(row)
    expected = 17 * (5.0 * 1.5 + 3.0 * 0.75 + 0.3 * 2 + 0.1 * 4 + 0.05 * 4 + 0.02 * 2 + 0.05 * 5 + 0.2 * 2)
    assert result["projected_points"] == pytest.approx(round(expected, 1), abs=0.2)
    assert result["floor"] < result["projected_points"] < result["ceiling"]


def test_project_kicker_distance_bonus_included():
    row = pd.Series(dict(
        games_proj=17, fg_made_pg=2.0, fg_40_49_pg=0.5, fg_50plus_pg=0.3,
        xp_made_pg=2.0, fg_missed_pg=0.2, xp_missed_pg=0.0, risk_tier="low",
    ))
    result = project_kicker(row)
    per_game = 2.0 * 1 + 0.5 * 1 + 0.3 * 2 + 2.0 * 1 + 0.2 * -1
    assert result["projected_points"] == pytest.approx(round(per_game * 17, 1))


def test_replacement_ranks_no_flex_for_idp_or_kicker():
    ranks = replacement_ranks(num_teams=16)
    assert ranks["DL"] == 16
    assert ranks["LB"] == 16
    assert ranks["DB"] == 16
    assert ranks["K"] == 16
    assert ranks["QB"] == 16


def test_replacement_ranks_rb_gets_biggest_flex_share():
    # Empirically measured (see tests/test_value_flex_share.py): RB wins
    # ~50% of flex slots in this format despite only 1 dedicated slot,
    # because RB2s frequently outscore WR4s here. WR's 3 dedicated slots
    # mean it still has a much deeper replacement rank overall, just not
    # from flex share dominance.
    ranks = replacement_ranks(num_teams=16)
    # 1 dedicated RB + 50% of 16 flex slots = 16 + 8 = 24
    assert ranks["RB"] == pytest.approx(24, abs=1)
    # 3 dedicated WR + 31.25% of 16 flex slots = 48 + 5 = 53
    assert ranks["WR"] == pytest.approx(53, abs=1)
    assert ranks["RB"] < ranks["WR"], "WR still has the deeper replacement rank overall (3 dedicated slots)"


def test_compute_vor_elite_player_beats_replacement_level_player():
    df = pd.DataFrame([
        {"player_name": f"LB{i}", "position": "LB", "projected_points": 250 - i * 10}
        for i in range(20)
    ])
    out = compute_vor(df, num_teams=16)
    best = out[out.player_name == "LB0"].iloc[0]
    replacement = out[out.player_name == "LB15"].iloc[0]  # 16th-ranked LB = replacement level
    assert best["vor"] > 0
    assert replacement["vor"] == pytest.approx(0, abs=0.01)
    assert best["overall_rank"] < replacement["overall_rank"]


def test_optimal_lineup_points_fills_flex_with_best_remaining():
    roster = [
        {"position": "QB", "projected_points": 300},
        {"position": "RB", "projected_points": 200},
        {"position": "RB", "projected_points": 150},  # should fill FLEX
        {"position": "WR", "projected_points": 250},
        {"position": "WR", "projected_points": 200},
        {"position": "WR", "projected_points": 150},
        {"position": "TE", "projected_points": 100},
        {"position": "DL", "projected_points": 80},
        {"position": "LB", "projected_points": 90},
        {"position": "DB", "projected_points": 70},
        {"position": "K", "projected_points": 60},
    ]
    total = optimal_lineup_points(roster)
    assert total == pytest.approx(300 + 200 + 150 + 250 + 200 + 150 + 100 + 80 + 90 + 70 + 60)


def test_simulate_draft_respects_roster_position_caps():
    # 20 QBs available but cap is 3 per roster -- no team should end up with more than 3.
    pool = pd.DataFrame([
        {"player_name": f"QB{i}", "position": "QB", "projected_points": 300 - i}
        for i in range(20)
    ] + [
        {"player_name": f"WR{i}", "position": "WR", "projected_points": 200 - i}
        for i in range(60)
    ])
    pool = compute_vor(pool, num_teams=4)
    rosters = simulate_draft(pool, num_teams=4, rounds=6)
    for roster in rosters.values():
        qb_count = sum(1 for p in roster if p["position"] == "QB")
        assert qb_count <= 3
