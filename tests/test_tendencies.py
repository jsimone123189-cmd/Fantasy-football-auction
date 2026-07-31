import pandas as pd

from draft_helper.analysis.tendencies import build_tendency_profiles, format_profile_text


def make_df():
    rows = [
        # Season 2022: Alice goes heavy RB early, Bob balanced, spends late.
        dict(season="2022", team_name="A", manager_name="Alice", manager_guid="g1",
             player_name="RB1", position="RB", cost=80, pick=1, is_keeper=False),
        dict(season="2022", team_name="A", manager_name="Alice", manager_guid="g1",
             player_name="RB2", position="RB", cost=60, pick=2, is_keeper=False),
        dict(season="2022", team_name="A", manager_name="Alice", manager_guid="g1",
             player_name="WR1", position="WR", cost=10, pick=15, is_keeper=False),
        dict(season="2022", team_name="B", manager_name="Bob", manager_guid="g2",
             player_name="QB1", position="QB", cost=20, pick=10, is_keeper=False),
        dict(season="2022", team_name="B", manager_name="Bob", manager_guid="g2",
             player_name="WR2", position="WR", cost=20, pick=12, is_keeper=False),
        dict(season="2022", team_name="B", manager_name="Bob", manager_guid="g2",
             player_name="RB3", position="RB", cost=20, pick=14, is_keeper=False),
        # Season 2023: Alice keeps a player.
        dict(season="2023", team_name="A", manager_name="Alice", manager_guid="g1",
             player_name="RB1", position="RB", cost=10, pick=1, is_keeper=True),
        dict(season="2023", team_name="A", manager_name="Alice", manager_guid="g1",
             player_name="WR3", position="WR", cost=30, pick=8, is_keeper=False),
        dict(season="2023", team_name="B", manager_name="Bob", manager_guid="g2",
             player_name="QB2", position="QB", cost=25, pick=5, is_keeper=False),
        dict(season="2023", team_name="B", manager_name="Bob", manager_guid="g2",
             player_name="RB4", position="RB", cost=25, pick=6, is_keeper=False),
    ]
    return pd.DataFrame(rows)


def test_build_tendency_profiles_basic_shape():
    df = make_df()
    profiles = build_tendency_profiles(df)
    assert set(profiles["manager_name"]) == {"Alice", "Bob"}
    assert (profiles["num_seasons"] == 2).all()

    alice = profiles[profiles["manager_name"] == "Alice"].iloc[0]
    assert alice["num_picks"] == 5
    assert alice["total_spend"] == 80 + 60 + 10 + 10 + 30
    assert alice["keeper_rate"] == 1 / 5

    bob = profiles[profiles["manager_name"] == "Bob"].iloc[0]
    assert bob["keeper_rate"] == 0
    assert pd.isna(bob["avg_keeper_cost"])


def test_alice_is_more_rb_heavy_than_bob():
    df = make_df()
    profiles = build_tendency_profiles(df)
    alice = profiles[profiles["manager_name"] == "Alice"].iloc[0]
    bob = profiles[profiles["manager_name"] == "Bob"].iloc[0]
    assert alice["position_shares"]["RB"] > bob["position_shares"]["RB"]


def test_format_profile_text_runs_without_error():
    df = make_df()
    profiles = build_tendency_profiles(df)
    for _, row in profiles.iterrows():
        text = format_profile_text(row)
        assert row["manager_name"] in text
