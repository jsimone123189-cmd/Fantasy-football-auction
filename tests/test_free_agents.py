import pandas as pd

from draft_helper.analysis.free_agents import compute_free_agents, normalize_name


def test_normalize_name_strips_suffix_and_punctuation():
    assert normalize_name("Kyle Pitts Sr.") == "kyle pitts"
    assert normalize_name("Kyle Pitts") == "kyle pitts"
    assert normalize_name("Marvin Harrison Jr.") == "marvin harrison"
    assert normalize_name("D'Andre Swift") == "dandre swift"
    assert normalize_name("A.J. Brown") == "aj brown"


def test_compute_free_agents_excludes_suffix_variants():
    draft_df = pd.DataFrame({"player_name": ["Kyle Pitts Sr.", "Aaron Jones Sr."]})
    projections_df = pd.DataFrame({
        "player_name": ["Kyle Pitts", "Aaron Jones", "Tyrone Tracy Jr."],
        "position": ["TE", "RB", "RB"],
        "projected_points": [111.1, 106.6, 171.8],
        "target_price": [10.8, 6.2, 13.9],
    })

    fa = compute_free_agents(draft_df, projections_df)

    assert list(fa["player_name"]) == ["Tyrone Tracy Jr."]


def test_compute_free_agents_sorted_by_value_descending():
    draft_df = pd.DataFrame({"player_name": []})
    projections_df = pd.DataFrame({
        "player_name": ["Low Value", "High Value"],
        "position": ["WR", "WR"],
        "projected_points": [10.0, 90.0],
        "target_price": [1.0, 9.0],
    })

    fa = compute_free_agents(draft_df, projections_df)

    assert list(fa["player_name"]) == ["High Value", "Low Value"]
