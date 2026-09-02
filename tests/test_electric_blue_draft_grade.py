import pandas as pd

from draft_helper.electric_blue.draft_grade import GRADE_BANDS, compute_needs, grade_draft


def _projections():
    return pd.DataFrame([
        {"player_name": "Elite RB", "position": "RB", "projected_points": 300, "overall_rank": 1},
        {"player_name": "Good WR", "position": "WR", "projected_points": 200, "overall_rank": 20},
        {"player_name": "Fine QB", "position": "QB", "projected_points": 250, "overall_rank": 50},
        {"player_name": "Late Steal", "position": "WR", "projected_points": 150, "overall_rank": 40},
        {"player_name": "Reach Pick", "position": "RB", "projected_points": 80, "overall_rank": 150},
        {"player_name": "Old Keeper", "position": "TE", "projected_points": 100, "overall_rank": 60},
    ])


def test_value_delta_rewards_getting_a_player_later_than_his_rank():
    # "Late Steal" (real rank 40) taken with pick 100 -- a big real value pick.
    picks = pd.DataFrame([
        {"pick": 1, "team_name": "A", "player_name": "Elite RB", "position": "RB"},
        {"pick": 100, "team_name": "A", "player_name": "Late Steal", "position": "WR"},
        {"pick": 20, "team_name": "B", "player_name": "Good WR", "position": "WR"},
        {"pick": 30, "team_name": "B", "player_name": "Reach Pick", "position": "RB"},
    ])
    grades = grade_draft(picks, _projections(), starting_slots={"RB": 1, "WR": 1}, flex_slots=0)
    team_a = grades[grades.team_name == "A"].iloc[0]
    team_b = grades[grades.team_name == "B"].iloc[0]
    assert team_a["value_surplus"] > team_b["value_surplus"]
    assert team_a["best_value_name"] == "Late Steal"
    assert team_b["worst_value_name"] == "Reach Pick"


def test_keepers_are_excluded_from_value_but_count_toward_roster():
    # "Old Keeper" was picked way ahead of its real rank (60), but it's a
    # keeper -- shouldn't be punished as a bad-value reach.
    picks = pd.DataFrame([
        {"pick": 1, "team_name": "A", "player_name": "Elite RB", "position": "RB", "is_keeper": False},
        {"pick": 5, "team_name": "A", "player_name": "Old Keeper", "position": "TE", "is_keeper": True},
    ])
    grades = grade_draft(picks, _projections(), starting_slots={"RB": 1, "TE": 1}, flex_slots=0)
    row = grades.iloc[0]
    assert row["best_value_name"] != "Old Keeper"
    assert row["worst_value_name"] != "Old Keeper"
    # still shows up in roster/starting points
    assert row["starting_points"] == 300 + 100


def test_optimal_lineup_uses_flex_for_best_remaining():
    picks = pd.DataFrame([
        {"pick": 1, "team_name": "A", "player_name": "Elite RB", "position": "RB"},
        {"pick": 2, "team_name": "A", "player_name": "Reach Pick", "position": "RB"},
        {"pick": 3, "team_name": "A", "player_name": "Good WR", "position": "WR"},
    ])
    grades = grade_draft(picks, _projections(), starting_slots={"RB": 1, "WR": 1}, flex_slots=1)
    row = grades.iloc[0]
    # RB1 (Elite RB) + WR1 (Good WR) + FLEX (Reach Pick, best remaining RB/WR/TE)
    assert row["starting_points"] == 300 + 200 + 80


def test_compute_needs_reports_open_dedicated_and_flex():
    team_df = pd.DataFrame([
        {"pick": 1, "position": "RB"},
    ])
    needs = compute_needs(team_df, {"RB": 1, "WR": 1}, flex_n=1)
    assert needs == "needs WR, FLEX"


def test_compute_needs_full_starting_lineup():
    team_df = pd.DataFrame([
        {"pick": 1, "position": "RB"},
        {"pick": 2, "position": "WR"},
        {"pick": 3, "position": "TE"},
    ])
    needs = compute_needs(team_df, {"RB": 1, "WR": 1}, flex_n=1)
    assert needs == "starting lineup full"


def test_grade_draft_sorted_best_first_and_bands_assigned():
    picks = pd.DataFrame([
        {"pick": 1, "team_name": "Strong", "player_name": "Elite RB", "position": "RB"},
        {"pick": 100, "team_name": "Strong", "player_name": "Late Steal", "position": "WR"},
        {"pick": 30, "team_name": "Weak", "player_name": "Reach Pick", "position": "RB"},
    ])
    grades = grade_draft(picks, _projections(), starting_slots={"RB": 1, "WR": 1}, flex_slots=0)
    assert list(grades.team_name) == ["Strong", "Weak"]
    valid_letters = {letter for _, letter in GRADE_BANDS} | {"F"}
    assert grades.iloc[0]["grade"] in valid_letters
    assert grades.iloc[1]["grade"] in valid_letters
