import pandas as pd

from draft_helper.analysis.draft_grade import grade_draft

SLOTS = {"QB": 1, "RB": 1, "WR": 1, "TE": 1, "DEF": 1, "FLEX": 2}


def _proj(rows):
    return pd.DataFrame(rows, columns=["player_name", "projected_points", "baseline_value"])


def _log(rows):
    return pd.DataFrame(rows, columns=["player_name", "position", "team_name", "cost"])


def test_grades_all_teams_and_sorts_best_first():
    log = _log([
        ("QB1", "QB", "Alice", 20), ("RB1", "RB", "Alice", 40), ("WR1", "WR", "Alice", 30),
        ("TE1", "TE", "Alice", 10), ("DEF1", "DEF", "Alice", 1), ("RB2", "RB", "Alice", 20),
        ("QB2", "QB", "Bob", 5), ("RB3", "RB", "Bob", 5), ("WR2", "WR", "Bob", 5),
        ("TE2", "TE", "Bob", 1), ("DEF2", "DEF", "Bob", 1), ("RB4", "RB", "Bob", 1),
    ])
    proj = _proj([
        ("QB1", 300, 20), ("RB1", 250, 40), ("WR1", 200, 30), ("TE1", 100, 10), ("DEF1", 80, 1), ("RB2", 150, 20),
        ("QB2", 100, 5), ("RB3", 50, 5), ("WR2", 50, 5), ("TE2", 30, 1), ("DEF2", 40, 1), ("RB4", 20, 1),
    ])
    grades = grade_draft(log, proj, SLOTS)
    assert set(grades["team_name"]) == {"Alice", "Bob"}
    assert grades.iloc[0]["team_name"] == "Alice"
    assert grades.iloc[0]["percentile"] > grades.iloc[1]["percentile"]


def test_does_not_penalize_skipping_backup_def():
    # Two teams with IDENTICAL starting lineups and equal-value bench spend --
    # one banks a bench RB, the other a bench DEF. Grades must match exactly:
    # the tool must not treat "no backup DEF" as a structural penalty.
    common = [
        ("QB1", "QB", None, 20), ("RB1", "RB", None, 40), ("WR1", "WR", None, 30),
        ("TE1", "TE", None, 10), ("DEF1", "DEF", None, 1), ("RB2", "RB", None, 15), ("WR2", "WR", None, 15),
    ]

    def with_team(rows, team):
        return [(n, p, team, c) for n, p, _, c in rows]

    log = _log(
        with_team(common, "BenchRB") + [("RB3", "RB", "BenchRB", 5)]
        + with_team(common, "BenchDEF") + [("DEF2", "DEF", "BenchDEF", 5)]
    )
    proj = _proj([
        ("QB1", 300, 20), ("RB1", 250, 40), ("WR1", 200, 30), ("TE1", 100, 10), ("DEF1", 80, 1),
        ("RB2", 120, 15), ("WR2", 120, 15),
        ("RB3", 40, 5), ("DEF2", 40, 5),
    ])
    grades = grade_draft(log, proj, SLOTS).set_index("team_name")
    assert grades.loc["BenchRB", "starting_points"] == grades.loc["BenchDEF", "starting_points"]
    assert grades.loc["BenchRB", "value_surplus"] == grades.loc["BenchDEF", "value_surplus"]
    assert grades.loc["BenchRB", "grade"] == grades.loc["BenchDEF", "grade"]


def test_value_surplus_rewards_bargains():
    log = _log([
        ("QB1", "QB", "Bargain", 5), ("RB1", "RB", "Bargain", 5), ("WR1", "WR", "Bargain", 5),
        ("TE1", "TE", "Bargain", 5), ("DEF1", "DEF", "Bargain", 1),
        ("QB2", "QB", "Overpay", 40), ("RB2", "RB", "Overpay", 40), ("WR2", "WR", "Overpay", 40),
        ("TE2", "TE", "Overpay", 40), ("DEF2", "DEF", "Overpay", 1),
    ])
    proj = _proj([
        ("QB1", 200, 40), ("RB1", 200, 40), ("WR1", 200, 40), ("TE1", 100, 20), ("DEF1", 80, 5),
        ("QB2", 200, 40), ("RB2", 200, 40), ("WR2", 200, 40), ("TE2", 100, 20), ("DEF2", 80, 5),
    ])
    grades = grade_draft(log, proj, {"QB": 1, "RB": 1, "WR": 1, "TE": 1, "DEF": 1, "FLEX": 0}).set_index("team_name")
    assert grades.loc["Bargain", "starting_points"] == grades.loc["Overpay", "starting_points"]
    assert grades.loc["Bargain", "value_surplus"] > grades.loc["Overpay", "value_surplus"]
    assert grades.loc["Bargain", "percentile"] > grades.loc["Overpay", "percentile"]


def test_missing_projection_defaults_to_zero_points_not_error():
    log = _log([("Mystery Player", "RB", "Solo", 3), ("DEF1", "DEF", "Solo", 1)])
    proj = _proj([("DEF1", 80, 1)])
    grades = grade_draft(log, proj, {"QB": 0, "RB": 1, "WR": 0, "TE": 0, "DEF": 1, "FLEX": 0})
    assert len(grades) == 1
    assert grades.iloc[0]["roster_points"] == 80
