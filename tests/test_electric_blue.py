import pandas as pd
import pytest

from draft_helper.electric_blue.scoring import (
    expected_milestone_bonus, score_defense, score_kicker, score_offense,
)
from draft_helper.electric_blue.dename import (
    apply as dename_apply, load_season_rosters, resolve_manager, resolve_team_name,
)
from draft_helper.electric_blue.parse_history import parse_file, PICK_RE
from draft_helper.electric_blue.value import compute_vor, replacement_ranks
from draft_helper.electric_blue.tendencies import (
    def_and_kicker_draft_rounds, manager_profiles, reach_index, reach_summary,
)


def test_score_offense_half_ppr():
    pts = score_offense(dict(receptions=5, rec_yards=50, rush_yards=100, rush_td=1))
    assert pts == pytest.approx(5 * 0.5 + 50 * 0.1 + 100 * 0.1 + 6)


def test_score_offense_interception_is_minus_one():
    # Confirmed real rule: -1 INT here, not -2 like Top Teamz/Rivals.
    pts = score_offense(dict(pass_yards=300, interceptions=1))
    assert pts == pytest.approx(300 * 0.04 - 1)


def test_kicker_scoring_flat_under_40_tiered_above():
    pts = score_kicker(fg_under_40=2, fg_40_49=1, fg_50plus=1, xp_made=3)
    assert pts == pytest.approx(2 * 3 + 1 * 4 + 1 * 5 + 3 * 1)


def test_defense_scoring_has_no_yards_allowed_tier():
    # Only points-allowed matters here, unlike Top Teamz which also scores yards allowed.
    pts = score_defense(sacks=3, interceptions=1, fumble_rec=1, def_td=0, points_allowed_pg=10, games=1)
    assert pts == pytest.approx(3 * 1 + 1 * 2 + 1 * 2 + 4)  # 10 pts allowed -> 7-13 tier = 4


def test_receiving_yards_have_a_milestone_bonus_unlike_top_teamz():
    bonus = expected_milestone_bonus(games=17, rec_ypg=150)
    assert bonus > 0


def test_pick_line_regex_handles_periods_in_names():
    m = PICK_RE.match("3.    C.J. Stroud    By The Beard...")
    assert m is not None
    assert m.group(2) == "C.J. Stroud"
    assert m.group(3) == "By The Beard..."


def test_parse_file_extracts_rounds_and_overall_pick(tmp_path):
    p = tmp_path / "2099.txt"
    p.write_text("league_id: test\nRound 1\n1.    Player A    Team X\n12.    Player L    Team Y\nRound 2\n1.    Player M    Team X\n")
    rows = parse_file(str(p), season=2099)
    assert len(rows) == 3
    assert rows[0]["overall_pick"] == 1
    assert rows[1]["overall_pick"] == 12
    assert rows[2]["overall_pick"] == 13  # round 2 pick 1 = 12*1 + 1


def test_dename_resolves_known_truncated_names(tmp_path):
    managers_csv = tmp_path / "managers.csv"
    managers_csv.write_text(
        "season,team_name,manager\n"
        "2020,By The Beard of Zeus,Jamison\n"
        "2020,Password Is Taco,Dave\n"
    )
    rosters = load_season_rosters(str(managers_csv))
    assert resolve_team_name(2020, "By The Beard...", rosters) == "By The Beard of Zeus"
    assert resolve_manager(2020, "By The Beard...", rosters) == "Jamison"
    assert resolve_manager(2020, "Password Is ...", rosters) == "Dave"


def test_dename_leaves_unresolved_names_as_partial(tmp_path):
    managers_csv = tmp_path / "managers.csv"
    managers_csv.write_text("season,team_name,manager\n2020,By The Beard of Zeus,Jamison\n")
    rosters = load_season_rosters(str(managers_csv))
    assert resolve_team_name(2020, "Some Unknown Team...", rosters) == "Some Unknown Team"
    assert resolve_manager(2020, "Some Unknown Team...", rosters) is None


def test_dename_passthrough_for_already_full_names(tmp_path):
    managers_csv = tmp_path / "managers.csv"
    managers_csv.write_text("season,team_name,manager\n2020,By The Beard of Zeus,Jamison\n")
    rosters = load_season_rosters(str(managers_csv))
    assert resolve_team_name(2020, "Wild Bill", rosters) == "Wild Bill"


def test_dename_is_season_specific_not_global(tmp_path):
    # Same truncated prefix resolves differently in different seasons if
    # the underlying full team name changed -- a real scenario in this
    # league's history (many teams renamed across years).
    managers_csv = tmp_path / "managers.csv"
    managers_csv.write_text(
        "season,team_name,manager\n"
        "2019,Zeke and Deztroyer,Alex\n"
        "2020,Zeke and Destroy!,Alex S\n"
    )
    rosters = load_season_rosters(str(managers_csv))
    assert resolve_team_name(2019, "Zeke and...", rosters) == "Zeke and Deztroyer"
    assert resolve_team_name(2020, "Zeke and...", rosters) == "Zeke and Destroy!"


def test_dename_apply_resolves_every_real_historical_pick():
    # Real-data regression check: every one of the ~1,236 historical picks
    # in draft_history_raw.csv should resolve to a real manager via the
    # per-season roster captures, with zero unmatched rows.
    df = pd.read_csv("data/electric_blue/draft_history_raw.csv")
    out = dename_apply(df)
    assert out["manager"].isna().sum() == 0
    assert out["manager"].nunique() >= 12  # at least the 12 real managers who've ever been in this league


def test_manager_profiles_covers_every_manager_not_just_stable_four():
    df = pd.read_csv("data/electric_blue/draft_history_raw.csv")
    df = dename_apply(df)
    profiles = manager_profiles(df)
    # Previously only 4 managers were confidently resolved; the per-season
    # roster data should now cover everyone who's ever drafted in this league.
    assert len(profiles) > 4
    assert "Jamison" in profiles["manager"].values


def test_reach_index_leave_one_out_excludes_self():
    df = pd.DataFrame([
        {"manager": "A", "player_name": "Star Player", "season": 2019, "round": 1},
        {"manager": "B", "player_name": "Star Player", "season": 2020, "round": 3},
        {"manager": "C", "player_name": "Star Player", "season": 2021, "round": 5},
    ])
    out = reach_index(df, min_appearances=2)
    row_a = out[out.manager == "A"].iloc[0]
    # A's field_avg should be the mean of B and C's rounds only (3,5 -> 4), not including A's own round 1.
    assert row_a["field_avg_round"] == pytest.approx(4.0)
    assert row_a["reach_rounds"] == pytest.approx(3.0)  # took him 3 rounds earlier than the field typically has


def test_reach_index_ignores_players_drafted_only_once():
    df = pd.DataFrame([
        {"manager": "A", "player_name": "One Timer", "season": 2019, "round": 5},
    ])
    out = reach_index(df, min_appearances=2)
    assert out.empty


def test_reach_summary_flags_consistent_early_drafter():
    df = pd.DataFrame([
        {"manager": "Reacher", "player_name": f"Player{i}", "season": 2019, "round": 2}
        for i in range(4)
    ] + [
        {"manager": "Other", "player_name": f"Player{i}", "season": 2020, "round": 6}
        for i in range(4)
    ])
    ridx = reach_index(df, min_appearances=2)
    summary = reach_summary(ridx, min_instances=3)
    reacher_row = summary[summary.manager == "Reacher"].iloc[0]
    assert reacher_row["avg_reach_rounds"] > 0
    other_row = summary[summary.manager == "Other"].iloc[0]
    assert other_row["avg_reach_rounds"] < 0


def test_replacement_ranks_no_flex_share_for_def_or_k():
    ranks = replacement_ranks(num_teams=12)
    assert ranks["K"] == 12
    assert ranks["DEF"] == 12
    assert ranks["QB"] == 12


def test_replacement_ranks_two_dedicated_rb_and_wr_slots():
    ranks = replacement_ranks(num_teams=12)
    # 2 dedicated + 40% of 12 flex slots = 24 + 4.8 ~= 29
    assert ranks["RB"] == pytest.approx(29, abs=1)
    assert ranks["WR"] == pytest.approx(29, abs=1)


def test_compute_vor_orders_by_value_over_replacement():
    df = pd.DataFrame([
        {"player_name": f"K{i}", "position": "K", "projected_points": 200 - i * 5}
        for i in range(15)
    ])
    out = compute_vor(df, num_teams=12)
    best = out[out.player_name == "K0"].iloc[0]
    replacement = out[out.player_name == "K11"].iloc[0]  # 12th K = replacement level
    assert best["vor"] > 0
    assert replacement["vor"] == pytest.approx(0, abs=0.01)


def test_def_and_kicker_draft_rounds_flags_late_market_behavior():
    df = pd.DataFrame([
        {"player_name": "Bills", "round": 9, "team_name": "X"},
        {"player_name": "Justin Tucker", "round": 13, "team_name": "X"},
        {"player_name": "Josh Allen", "round": 1, "team_name": "X"},
    ])
    result = def_and_kicker_draft_rounds(df)
    assert result["def_earliest_round"] == 9
    assert result["kicker_avg_round"] == 13
