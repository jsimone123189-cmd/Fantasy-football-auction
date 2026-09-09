import pandas as pd

from draft_helper.rivals.build_idp_inputs import _derive


POS_MEANS = {
    "tfl_2025": 0.05, "sacks_2025": 0.02, "ff_2025": 0.01,
    "fr_2025": 0.01, "int_2025": 0.0, "pd_2025": 0.02,
}


def _row(**overrides):
    base = {
        "player_name": "Test Player", "position": "DL", "nfl_team": "PIT",
        "games_played_2025": 17.0, "solo_tackles_2025": 30.0, "ast_tackles_2025": 20.0,
        "tfl_2025": 5.0, "sacks_2025": 3.0, "ff_2025": 1.0, "fr_2025": 0.0,
        "int_2025": 0.0, "pd_2025": 2.0, "role_2026": "Starter", "depth_chart_note": "",
        "risk_tier": "medium",
    }
    base.update(overrides)
    return pd.Series(base)


def test_derive_keeps_player_with_unresolved_retirement_speculation():
    # Real case: Cameron Heyward -- retirement was speculated, then he re-signed.
    # A player who didn't retire must not be filtered out just because the
    # word "retirement" appears in his notes.
    row = _row(depth_chart_note="Retirement speculation after playoff loss, but he re-signed a 2-year deal.")

    result = _derive(row, solo_share=0.5, pos_means=POS_MEANS)

    assert result is not None
    assert result["player_name"] == "Test Player"


def test_derive_drops_a_confirmed_retired_player():
    row = _row(role_2026="N/A -- retired", depth_chart_note="Retired after 11 NFL seasons.")

    result = _derive(row, solo_share=0.5, pos_means=POS_MEANS)

    assert result is None
