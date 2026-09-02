import pandas as pd

from draft_helper.electric_blue.grade_report import generate_html


def _grades():
    return pd.DataFrame([
        {
            "team_name": "Alice", "starting_points": 1500.0, "roster_points": 1800.0,
            "value_surplus": 42.0, "best_value_name": "Late Steal", "best_value_delta": 30.0,
            "worst_value_name": "Reach Guy", "worst_value_delta": -10.0, "needs": "starting lineup full",
            "percentile": 0.9, "grade": "A",
        },
        {
            "team_name": "Bob", "starting_points": 1200.0, "roster_points": 1500.0,
            "value_surplus": -20.0, "best_value_name": "OK Pick", "best_value_delta": 5.0,
            "worst_value_name": "Bad Reach", "worst_value_delta": -25.0, "needs": "needs TE",
            "percentile": 0.2, "grade": "D",
        },
    ])


def test_generate_html_includes_team_rows_and_pick_value_language():
    out = generate_html(_grades(), title="Test EB Grades")
    assert "Test EB Grades" in out
    assert "Alice" in out and "Bob" in out
    assert "pick-slot value" in out
    assert "+42" in out
    assert "-20" in out
    assert "needs TE" in out


def test_generate_html_escapes_team_names():
    grades = pd.DataFrame([{
        "team_name": "<script>alert(1)</script>", "starting_points": 100.0,
        "roster_points": 100.0, "value_surplus": 0.0, "best_value_name": "X", "best_value_delta": 0.0,
        "worst_value_name": "Y", "worst_value_delta": 0.0, "needs": "", "percentile": 0.5, "grade": "C",
    }])
    out = generate_html(grades)
    assert "<script>alert(1)</script>" not in out
    assert "&lt;script&gt;" in out
